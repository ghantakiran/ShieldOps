"""LangGraph workflow definition for the PlatformIntelligence Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.platform_intelligence.models import PlatformIntelligenceState
from shieldops.agents.platform_intelligence.nodes import (
    analyze_patterns,
    compute_insights,
    finalize_intelligence,
    gather_telemetry,
    generate_strategy,
)
from shieldops.agents.tracing import traced_node


def should_continue(state: PlatformIntelligenceState) -> str:
    """Check if workflow should continue or finalize."""
    if state.error:
        return "finalize_intelligence"
    return "analyze_patterns"


def create_platform_intelligence_graph() -> StateGraph[PlatformIntelligenceState]:
    """Build the PlatformIntelligence Agent LangGraph workflow."""
    graph = StateGraph(PlatformIntelligenceState)

    _agent = "platform_intelligence"
    graph.add_node(
        "gather_telemetry",
        traced_node("platform_intelligence.gather_telemetry", _agent)(gather_telemetry),
    )
    graph.add_node(
        "analyze_patterns",
        traced_node("platform_intelligence.analyze_patterns", _agent)(analyze_patterns),
    )
    graph.add_node(
        "compute_insights",
        traced_node("platform_intelligence.compute_insights", _agent)(compute_insights),
    )
    graph.add_node(
        "generate_strategy",
        traced_node("platform_intelligence.generate_strategy", _agent)(generate_strategy),
    )
    graph.add_node(
        "finalize_intelligence",
        traced_node("platform_intelligence.finalize_intelligence", _agent)(finalize_intelligence),
    )

    graph.set_entry_point("gather_telemetry")
    graph.add_conditional_edges(
        "gather_telemetry",
        should_continue,
        {
            "analyze_patterns": "analyze_patterns",
            "finalize_intelligence": "finalize_intelligence",
        },
    )
    graph.add_edge("analyze_patterns", "compute_insights")
    graph.add_edge("compute_insights", "generate_strategy")
    graph.add_edge("generate_strategy", "finalize_intelligence")
    graph.add_edge("finalize_intelligence", END)

    return graph
