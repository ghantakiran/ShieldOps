"""LangGraph workflow definition for the Auto Remediation Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.auto_remediation.models import AutoRemediationState
from shieldops.agents.auto_remediation.nodes import (
    assess_issue,
    execute_fix,
    finalize_remediation,
    plan_remediation,
    verify_resolution,
)
from shieldops.agents.tracing import traced_node


def should_continue(state: AutoRemediationState) -> str:
    """Check if workflow should continue or finalize."""
    if state.error:
        return "finalize_remediation"
    return "plan_remediation"


def create_auto_remediation_graph() -> StateGraph[AutoRemediationState]:
    """Build the Auto Remediation Agent LangGraph workflow."""
    graph = StateGraph(AutoRemediationState)

    _agent = "auto_remediation"
    graph.add_node(
        "assess_issue",
        traced_node("auto_remediation.assess_issue", _agent)(assess_issue),
    )
    graph.add_node(
        "plan_remediation",
        traced_node("auto_remediation.plan_remediation", _agent)(plan_remediation),
    )
    graph.add_node(
        "execute_fix",
        traced_node("auto_remediation.execute_fix", _agent)(execute_fix),
    )
    graph.add_node(
        "verify_resolution",
        traced_node("auto_remediation.verify_resolution", _agent)(verify_resolution),
    )
    graph.add_node(
        "finalize_remediation",
        traced_node("auto_remediation.finalize_remediation", _agent)(finalize_remediation),
    )

    graph.set_entry_point("assess_issue")
    graph.add_conditional_edges(
        "assess_issue",
        should_continue,
        {"plan_remediation": "plan_remediation", "finalize_remediation": "finalize_remediation"},
    )
    graph.add_edge("plan_remediation", "execute_fix")
    graph.add_edge("execute_fix", "verify_resolution")
    graph.add_edge("verify_resolution", "finalize_remediation")
    graph.add_edge("finalize_remediation", END)

    return graph
