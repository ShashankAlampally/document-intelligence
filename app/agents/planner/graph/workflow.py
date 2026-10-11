"""Main graph routes a request to the existing dedicated specialist graphs."""

from uuid import UUID

from app.agents.extraction.graph.extract_bid import extract_bid_fields
from app.agents.planner.graph.state import MainState
from app.agents.planner.nodes.choose_workflow import choose_workflow
from app.agents.qa.graph.workflow import answer_question
from app.tools.selected_uploads import selected_uploads


def route_request(state: MainState) -> str:
    if state.error:
        return "stop"
    return state.choice.task


def build_main_graph(model, available_tools: dict):
    from langgraph.graph import END, START, StateGraph

    def choose_step(state):
        return choose_workflow(state, model)

    def qa_step(state):
        result = answer_question(state.request, model, available_tools)
        return {
            "qa_result": result.model_copy(update={"trace": []}),
            "error": result.error,
            "trace": state.trace + result.trace,
        }

    def extraction_step(state):
        if len(state.discovery_ids) != 1:
            from app.agents.qa.models.answers import QuestionAnswer

            return {
                "qa_result": QuestionAnswer(
                    status="direct_response",
                    answer="Select one folder to extract its 20 fields. "
                    "For comparisons, ask a question.",
                )
            }
        result = extract_bid_fields(model, available_tools)
        return {
            "extraction_result": result.model_copy(update={"trace": []}),
            "error": result.error,
            "trace": state.trace + result.trace,
        }

    graph = StateGraph(MainState)
    graph.add_node("choose_workflow", choose_step)
    graph.add_node("qa_agent", qa_step)
    graph.add_node("extraction_agent", extraction_step)
    graph.add_edge(START, "choose_workflow")
    graph.add_conditional_edges(
        "choose_workflow",
        route_request,
        {
            "qa": "qa_agent",
            "extraction": "extraction_agent",
            "reply": END,
            "stop": END,
        },
    )
    graph.add_edge("qa_agent", END)
    graph.add_edge("extraction_agent", END)
    return graph.compile()


def run_request(
    request: str, discovery_id: UUID | list[UUID], model, available_tools: dict
) -> MainState:
    if not request.strip():
        raise ValueError("Request cannot be blank")
    ids = selected_uploads(discovery_id)
    tool = available_tools.get("search_documents")
    if tool is not None and hasattr(tool, "discovery_ids") and tool.discovery_ids != ids:
        raise ValueError("Search tool selection must match the request selection")
    graph = build_main_graph(model, available_tools)
    return MainState.model_validate(
        graph.invoke(
            MainState(request=request.strip(), discovery_ids=ids),
            config={"recursion_limit": 6},
        )
    )
