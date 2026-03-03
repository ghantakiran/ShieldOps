"""LangGraph workflow definition for the ObservabilityIntelligence Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.observability_intelligence.models import ObservabilityIntelligenceState
from shieldops.agents.observability_intelligence.nodes import (
    analyze_insights,
    collect_signals,
    correlate_data,
    finalize_analysis,
    generate_recommendations,
)
from shieldops.agents.tracing import traced_node


def should_continue(state: ObservabilityIntelligenceState) -> str:
    """Check if workflow should continue or finalize."""
    if state.error:
        return "finalize_analysis"
    return "correlate_data"


def create_observability_intelligence_graph() -> StateGraph[ObservabilityIntelligenceState]:
    """Build the ObservabilityIntelligence Agent LangGraph workflow."""
    graph = StateGraph(ObservabilityIntelligenceState)

    _agent = "observability_intelligence"
    graph.add_node(
        "collect_signals",
        traced_node("observability_intelligence.collect_signals", _agent)(collect_signals),
    )
    graph.add_node(
        "correlate_data",
        traced_node("observability_intelligence.correlate_data", _agent)(correlate_data),
    )
    graph.add_node(
        "analyze_insights",
        traced_node("observability_intelligence.analyze_insights", _agent)(analyze_insights),
    )
    graph.add_node(
        "generate_recommendations",
        traced_node(
            "observability_intelligence.generate_recommendations",
            _agent,
        )(generate_recommendations),
    )
    graph.add_node(
        "finalize_analysis",
        traced_node("observability_intelligence.finalize_analysis", _agent)(finalize_analysis),
    )

    graph.set_entry_point("collect_signals")
    graph.add_conditional_edges(
        "collect_signals",
        should_continue,
        {"correlate_data": "correlate_data", "finalize_analysis": "finalize_analysis"},
    )
    graph.add_edge("correlate_data", "analyze_insights")
    graph.add_edge("analyze_insights", "generate_recommendations")
    graph.add_edge("generate_recommendations", "finalize_analysis")
    graph.add_edge("finalize_analysis", END)

    return graph
