"""LangGraph workflow definition for the FinOps Intelligence Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.finops_intelligence.models import FinOpsIntelligenceState
from shieldops.agents.finops_intelligence.nodes import (
    analyze_costs,
    finalize_analysis,
    identify_optimizations,
    plan_implementation,
    prioritize_savings,
)
from shieldops.agents.tracing import traced_node


def should_optimize(state: FinOpsIntelligenceState) -> str:
    """Check if optimization is needed based on cost findings."""
    if state.error:
        return "finalize_analysis"
    if state.finding_count > 0:
        return "identify_optimizations"
    return "finalize_analysis"


def should_plan(state: FinOpsIntelligenceState) -> str:
    """Check if implementation planning is needed."""
    if state.high_impact_count > 0:
        return "plan_implementation"
    return "finalize_analysis"


def create_finops_intelligence_graph() -> StateGraph[FinOpsIntelligenceState]:
    """Build the FinOps Intelligence Agent LangGraph workflow.

    Workflow:
        analyze_costs -> [has_findings? -> identify_optimizations
            -> prioritize_savings]
            -> [high_impact? -> plan_implementation]
            -> finalize_analysis
    """
    graph = StateGraph(FinOpsIntelligenceState)

    _agent = "finops_intelligence"
    graph.add_node(
        "analyze_costs",
        traced_node("finops_intelligence.analyze_costs", _agent)(analyze_costs),
    )
    graph.add_node(
        "identify_optimizations",
        traced_node("finops_intelligence.identify_optimizations", _agent)(identify_optimizations),
    )
    graph.add_node(
        "prioritize_savings",
        traced_node("finops_intelligence.prioritize_savings", _agent)(prioritize_savings),
    )
    graph.add_node(
        "plan_implementation",
        traced_node("finops_intelligence.plan_implementation", _agent)(plan_implementation),
    )
    graph.add_node(
        "finalize_analysis",
        traced_node("finops_intelligence.finalize_analysis", _agent)(finalize_analysis),
    )

    # Define edges
    graph.set_entry_point("analyze_costs")
    graph.add_conditional_edges(
        "analyze_costs",
        should_optimize,
        {
            "identify_optimizations": "identify_optimizations",
            "finalize_analysis": "finalize_analysis",
        },
    )
    graph.add_edge("identify_optimizations", "prioritize_savings")
    graph.add_conditional_edges(
        "prioritize_savings",
        should_plan,
        {
            "plan_implementation": "plan_implementation",
            "finalize_analysis": "finalize_analysis",
        },
    )
    graph.add_edge("plan_implementation", "finalize_analysis")
    graph.add_edge("finalize_analysis", END)

    return graph
