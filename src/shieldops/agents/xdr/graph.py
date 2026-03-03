"""LangGraph workflow definition for the XDR Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.tracing import traced_node
from shieldops.agents.xdr.models import XDRState
from shieldops.agents.xdr.nodes import (
    build_attack_story,
    correlate_threats,
    execute_response,
    finalize_investigation,
    ingest_telemetry,
)


def should_continue(state: XDRState) -> str:
    """Check if workflow should continue or finalize."""
    if state.error:
        return "finalize_investigation"
    return "correlate_threats"


def create_xdr_graph() -> StateGraph[XDRState]:
    """Build the XDR Agent LangGraph workflow."""
    graph = StateGraph(XDRState)

    _agent = "xdr"
    graph.add_node(
        "ingest_telemetry",
        traced_node("xdr.ingest_telemetry", _agent)(ingest_telemetry),
    )
    graph.add_node(
        "correlate_threats",
        traced_node("xdr.correlate_threats", _agent)(correlate_threats),
    )
    graph.add_node(
        "build_attack_story",
        traced_node("xdr.build_attack_story", _agent)(build_attack_story),
    )
    graph.add_node(
        "execute_response",
        traced_node("xdr.execute_response", _agent)(execute_response),
    )
    graph.add_node(
        "finalize_investigation",
        traced_node("xdr.finalize_investigation", _agent)(finalize_investigation),
    )

    graph.set_entry_point("ingest_telemetry")
    graph.add_conditional_edges(
        "ingest_telemetry",
        should_continue,
        {
            "correlate_threats": "correlate_threats",
            "finalize_investigation": "finalize_investigation",
        },
    )
    graph.add_edge("correlate_threats", "build_attack_story")
    graph.add_edge("build_attack_story", "execute_response")
    graph.add_edge("execute_response", "finalize_investigation")
    graph.add_edge("finalize_investigation", END)

    return graph
