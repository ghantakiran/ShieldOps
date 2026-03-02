"""LangGraph workflow definition for the Attack Surface Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.attack_surface.models import AttackSurfaceState
from shieldops.agents.attack_surface.nodes import (
    analyze_exposures,
    discover_assets,
    finalize_scan,
    plan_remediation,
    prioritize_findings,
)
from shieldops.agents.tracing import traced_node


def should_analyze(state: AttackSurfaceState) -> str:
    """Check if analysis is needed based on discovery results."""
    if state.error:
        return "finalize_scan"
    if state.asset_count > 0:
        return "analyze_exposures"
    return "finalize_scan"


def should_remediate(state: AttackSurfaceState) -> str:
    """Check if remediation planning is needed."""
    if state.critical_count > 0:
        return "plan_remediation"
    return "finalize_scan"


def create_attack_surface_graph() -> StateGraph[AttackSurfaceState]:
    """Build the Attack Surface Agent LangGraph workflow.

    Workflow:
        discover_assets -> [has_assets? -> analyze_exposures -> prioritize_findings]
            -> [critical? -> plan_remediation]
            -> finalize_scan
    """
    graph = StateGraph(AttackSurfaceState)

    _agent = "attack_surface"
    graph.add_node(
        "discover_assets",
        traced_node("attack_surface.discover_assets", _agent)(discover_assets),
    )
    graph.add_node(
        "analyze_exposures",
        traced_node("attack_surface.analyze_exposures", _agent)(analyze_exposures),
    )
    graph.add_node(
        "prioritize_findings",
        traced_node("attack_surface.prioritize_findings", _agent)(prioritize_findings),
    )
    graph.add_node(
        "plan_remediation",
        traced_node("attack_surface.plan_remediation", _agent)(plan_remediation),
    )
    graph.add_node(
        "finalize_scan",
        traced_node("attack_surface.finalize_scan", _agent)(finalize_scan),
    )

    # Define edges
    graph.set_entry_point("discover_assets")
    graph.add_conditional_edges(
        "discover_assets",
        should_analyze,
        {"analyze_exposures": "analyze_exposures", "finalize_scan": "finalize_scan"},
    )
    graph.add_edge("analyze_exposures", "prioritize_findings")
    graph.add_conditional_edges(
        "prioritize_findings",
        should_remediate,
        {"plan_remediation": "plan_remediation", "finalize_scan": "finalize_scan"},
    )
    graph.add_edge("plan_remediation", "finalize_scan")
    graph.add_edge("finalize_scan", END)

    return graph
