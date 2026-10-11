"""Extraction graph with a single bounded field-correction loop."""

from langgraph.graph import END, START, StateGraph

from app.agents.extraction.graph.state import ExtractionState
from app.agents.extraction.nodes.correct_fields import correct_fields
from app.agents.extraction.nodes.extract_fields import extract_fields
from app.agents.extraction.nodes.validate_fields import validate_fields
from app.agents.shared.retrieve_evidence import retrieve_evidence


def after_validation(state):
    if state.error or state.correction_attempts:
        return "stop"
    if any(item.decision != "accepted" for item in state.validation.fields):
        return "correct"
    return "stop"


def build_extraction_graph(model, available_tools, on_step=None):
    graph = StateGraph(ExtractionState)
    graph.add_node("retrieve", lambda state: retrieve_evidence(state, available_tools))
    graph.add_node("extract", lambda state: extract_fields(state, model))
    graph.add_node("validate", lambda state: validate_fields(state, model, on_step=on_step))
    graph.add_node(
        "correct", lambda state: correct_fields(state, model, available_tools, on_step=on_step)
    )
    graph.add_edge(START, "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        lambda state: "stop" if state.error else "extract",
        {"stop": END, "extract": "extract"},
    )
    graph.add_conditional_edges(
        "extract",
        lambda state: "stop" if state.error else "validate",
        {"stop": END, "validate": "validate"},
    )
    graph.add_conditional_edges("validate", after_validation, {"stop": END, "correct": "correct"})
    graph.add_conditional_edges(
        "correct",
        lambda state: "stop" if state.error else "validate",
        {"stop": END, "validate": "validate"},
    )
    return graph.compile()


def build_validation_graph(model, available_tools, on_step=None):
    """Validate the complete draft, then correct rejected fields once."""
    graph = StateGraph(ExtractionState)
    graph.add_node("validate", lambda state: validate_fields(state, model, on_step=on_step))
    graph.add_node(
        "correct", lambda state: correct_fields(state, model, available_tools, on_step=on_step)
    )
    graph.add_edge(START, "validate")
    graph.add_conditional_edges("validate", after_validation, {"stop": END, "correct": "correct"})
    graph.add_conditional_edges(
        "correct",
        lambda state: "stop" if state.error else "validate",
        {"stop": END, "validate": "validate"},
    )
    return graph.compile()
