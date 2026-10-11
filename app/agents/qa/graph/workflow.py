"""Connect the Q&A steps used by the CLI and workspace API."""

from app.agents.qa.graph.state import WorkflowState
from app.agents.qa.models.answers import QuestionAnswer
from app.agents.qa.nodes.answer_or_search import answer_or_search
from app.agents.qa.nodes.generate_answer import generate_answer
from app.agents.qa.nodes.retrieve_qa_evidence import retrieve_qa_evidence
from app.agents.shared.select_evidence import EXTRACTION_MAX_CHARS, EXTRACTION_MAX_CHUNKS


def build_question_answer_graph(model, available_tools: dict):
    from langgraph.graph import END, START, StateGraph

    def initial_search(state):
        return retrieve_qa_evidence(state, available_tools)

    def decide(state):
        return answer_or_search(state, model)

    def additional_search(state):
        return retrieve_qa_evidence(state, available_tools, additional=True)

    def answer_step(state):
        return generate_answer(state, model)

    def after_search(state):
        if state.error:
            return "stop"
        return "continue"

    def after_decision(state):
        if state.error or state.decision.action == "answer":
            return "stop"
        return "search_more"

    graph = StateGraph(WorkflowState)
    graph.add_node("retrieve_evidence", initial_search)
    graph.add_node("answer_or_search", decide)
    graph.add_node("additional_search", additional_search)
    graph.add_node("generate_answer", answer_step)
    graph.add_edge(START, "retrieve_evidence")
    graph.add_conditional_edges(
        "retrieve_evidence", after_search, {"stop": END, "continue": "answer_or_search"}
    )
    graph.add_conditional_edges(
        "answer_or_search", after_decision, {"stop": END, "search_more": "additional_search"}
    )
    graph.add_conditional_edges(
        "additional_search", after_search, {"stop": END, "continue": "generate_answer"}
    )
    graph.add_edge("generate_answer", END)
    return graph.compile()


def answer_question(question: str, model, available_tools: dict) -> QuestionAnswer:
    if not question.strip():
        raise ValueError("Question cannot be blank")
    content = question.strip()
    tool = available_tools.get("search_documents")
    settings = getattr(tool, "settings", None)
    if tool is not None and hasattr(tool, "discovery_ids"):
        content += "\nSelected discovery IDs: " + ", ".join(map(str, tool.discovery_ids))
    graph = build_question_answer_graph(model, available_tools)
    state = WorkflowState.model_validate(
        graph.invoke(
            WorkflowState(
                search_queries=[question.strip()],
                search_top_k=getattr(settings, "qa_search_top_k", 5),
                max_followup_queries=getattr(settings, "qa_max_followup_queries", 6),
                max_evidence_chars=EXTRACTION_MAX_CHARS,
                max_evidence_chunks=EXTRACTION_MAX_CHUNKS,
                messages=[{"role": "user", "content": content}],
            ),
            config={"recursion_limit": 10},
        )
    )
    if state.error:
        return QuestionAnswer(
            status="error",
            answer="Unable to complete this request.",
            error=state.error,
            trace=state.trace,
        )
    draft = state.draft
    sources = {item["chunk_id"]: item for item in state.evidence}
    return QuestionAnswer(
        status=draft.status,
        answer=draft.answer,
        sources=[sources[key] for key in dict.fromkeys(draft.source_chunk_ids)],
        trace=state.trace,
    )
