"""LangGraph workflow definition for the Remediation Agent.

Workflow:
    evaluate_policy → [DENIED? → END]
    → assess_risk → [HIGH/CRITICAL? → request_approval → [DENIED? → END]]
    → create_snapshot → execute_action
    → [FAILED? → perform_rollback → END]
    → validate_health → [UNHEALTHY? → perform_rollback → END]
    → END (success)
"""

import structlog
from langgraph.graph import END, StateGraph

from shieldops.agents.remediation.models import RemediationState
from shieldops.agents.remediation.nodes import (
    assess_risk,
    create_snapshot,
    evaluate_policy,
    execute_action,
    perform_rollback,
    request_approval,
    validate_health,
)
from shieldops.models.base import ApprovalStatus, ExecutionStatus

logger = structlog.get_logger()


def policy_gate(state: RemediationState) -> str:
    """Route based on policy evaluation result."""
    if state.policy_result and state.policy_result.allowed:
        return "assess_risk"
    return END


def approval_gate(state: RemediationState) -> str:
    """Route based on risk level — high/critical need approval."""
    from shieldops.agents.remediation.nodes import _get_toolkit

    toolkit = _get_toolkit()
    if state.assessed_risk and toolkit.requires_approval(state.assessed_risk):
        return "request_approval"
    return "create_snapshot"


def approval_decision(state: RemediationState) -> str:
    """Route based on approval result."""
    if state.approval_status == ApprovalStatus.APPROVED:
        return "create_snapshot"
    return END


def execution_gate(state: RemediationState) -> str:
    """Route based on execution result — rollback on failure."""
    if state.execution_result and state.execution_result.status == ExecutionStatus.SUCCESS:
        return "validate_health"
    return "perform_rollback"


def validation_gate(state: RemediationState) -> str:
    """Route based on validation — rollback if unhealthy."""
    if state.validation_passed is True:
        return END
    if state.validation_passed is False:
        return "perform_rollback"
    # None = uncertain, proceed cautiously
    return END


def create_remediation_graph() -> StateGraph:
    """Build the Remediation Agent LangGraph workflow."""
    graph = StateGraph(RemediationState)

    # Add nodes
    graph.add_node("evaluate_policy", evaluate_policy)
    graph.add_node("assess_risk", assess_risk)
    graph.add_node("request_approval", request_approval)
    graph.add_node("create_snapshot", create_snapshot)
    graph.add_node("execute_action", execute_action)
    graph.add_node("validate_health", validate_health)
    graph.add_node("perform_rollback", perform_rollback)

    # Entry point
    graph.set_entry_point("evaluate_policy")

    # Policy gate: allowed → assess_risk, denied → END
    graph.add_conditional_edges(
        "evaluate_policy",
        policy_gate,
        {
            "assess_risk": "assess_risk",
            END: END,
        },
    )

    # Risk assessment → approval or direct execution
    graph.add_conditional_edges(
        "assess_risk",
        approval_gate,
        {
            "request_approval": "request_approval",
            "create_snapshot": "create_snapshot",
        },
    )

    # Approval decision → execute or abort
    graph.add_conditional_edges(
        "request_approval",
        approval_decision,
        {
            "create_snapshot": "create_snapshot",
            END: END,
        },
    )

    # Snapshot → execute
    graph.add_edge("create_snapshot", "execute_action")

    # Execution result → validate or rollback
    graph.add_conditional_edges(
        "execute_action",
        execution_gate,
        {
            "validate_health": "validate_health",
            "perform_rollback": "perform_rollback",
        },
    )

    # Validation → success or rollback
    graph.add_conditional_edges(
        "validate_health",
        validation_gate,
        {
            END: END,
            "perform_rollback": "perform_rollback",
        },
    )

    # Rollback always ends the workflow
    graph.add_edge("perform_rollback", END)

    return graph
