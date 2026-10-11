"""A shared two-step graph: direct retrieval, then specialist model output."""

from app.agents.shared.retrieve_evidence import retrieve_evidence


def route_after_retrieval(state) -> str:
    if state.error:
        return "stop"
    return "finish"


def build_retrieval_graph(state_model, available_tools: dict, finish_step):
    from langgraph.graph import END, START, StateGraph

    def search_step(state):
        return retrieve_evidence(state, available_tools)

    graph = StateGraph(state_model)
    graph.add_node("retrieve_evidence", search_step)
    graph.add_node("finish", finish_step)
    graph.add_edge(START, "retrieve_evidence")
    graph.add_conditional_edges(
        "retrieve_evidence", route_after_retrieval, {"stop": END, "finish": "finish"}
    )
    graph.add_edge("finish", END)
    return graph.compile()
