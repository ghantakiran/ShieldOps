"""LangGraph workflow definition for the Itdr Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.itdr.models import ITDRState
from shieldops.agents.itdr.nodes import (
    analyze_attack_paths,
    detect_threats,
    finalize_detection,
    respond_to_threats,
    scan_identities,
)
from shieldops.agents.tracing import traced_node


def should_continue(state: ITDRState) -> str:
    """Check if workflow should continue or finalize."""
    if state.error:
        return "finalize_detection"
    return "detect_threats"


def create_itdr_graph() -> StateGraph[ITDRState]:
    """Build the Itdr Agent LangGraph workflow."""
    graph = StateGraph(ITDRState)

    _agent = "itdr"
    graph.add_node(
        "scan_identities",
        traced_node("itdr.scan_identities", _agent)(scan_identities),
    )
    graph.add_node(
        "detect_threats",
        traced_node("itdr.detect_threats", _agent)(detect_threats),
    )
    graph.add_node(
        "analyze_attack_paths",
        traced_node("itdr.analyze_attack_paths", _agent)(analyze_attack_paths),
    )
    graph.add_node(
        "respond_to_threats",
        traced_node("itdr.respond_to_threats", _agent)(respond_to_threats),
    )
    graph.add_node(
        "finalize_detection",
        traced_node("itdr.finalize_detection", _agent)(finalize_detection),
    )

    graph.set_entry_point("scan_identities")
    graph.add_conditional_edges(
        "scan_identities",
        should_continue,
        {"detect_threats": "detect_threats", "finalize_detection": "finalize_detection"},
    )
    graph.add_edge("detect_threats", "analyze_attack_paths")
    graph.add_edge("analyze_attack_paths", "respond_to_threats")
    graph.add_edge("respond_to_threats", "finalize_detection")
    graph.add_edge("finalize_detection", END)

    return graph
