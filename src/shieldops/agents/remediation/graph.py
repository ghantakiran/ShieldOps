"""LangGraph workflow definition for the Remediation Agent.

Workflow:
    evaluate_policy → [DENIED? → END]
    → resolve_playbook → assess_risk
    → [HIGH/CRITICAL? → request_approval → [DENIED? → END]]
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
    resolve_playbook,
    validate_health,
)
from shieldops.agents.tracing import traced_node
from shieldops.models.base import ApprovalStatus, ExecutionStatus

logger = structlog.get_logger()


def policy_gate(state: RemediationState) -> str:
    """Route based on policy evaluation result."""
    if state.policy_result and state.policy_result.allowed:
        return "resolve_playbook"
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


def create_remediation_graph() -> StateGraph[RemediationState]:
    """Build the Remediation Agent LangGraph workflow."""
    graph = StateGraph(RemediationState)

    # Add nodes (wrapped with OTEL tracing spans)
    _rem = "remediation"
    graph.add_node(
        "evaluate_policy",
        traced_node("remediation.evaluate_policy", _rem)(evaluate_policy),
    )
    graph.add_node(
        "resolve_playbook",
        traced_node("remediation.resolve_playbook", _rem)(resolve_playbook),
    )
    graph.add_node(
        "assess_risk",
        traced_node("remediation.assess_risk", _rem)(assess_risk),
    )
    graph.add_node(
        "request_approval",
        traced_node("remediation.request_approval", _rem)(request_approval),
    )
    graph.add_node(
        "create_snapshot",
        traced_node("remediation.create_snapshot", _rem)(create_snapshot),
    )
    graph.add_node(
        "execute_action",
        traced_node("remediation.execute_action", _rem)(execute_action),
    )
    graph.add_node(
        "validate_health",
        traced_node("remediation.validate_health", _rem)(validate_health),
    )
    graph.add_node(
        "perform_rollback",
        traced_node("remediation.perform_rollback", _rem)(perform_rollback),
    )

    # Entry point
    graph.set_entry_point("evaluate_policy")

    # Policy gate: allowed → resolve_playbook, denied → END
    graph.add_conditional_edges(
        "evaluate_policy",
        policy_gate,
        {
            "resolve_playbook": "resolve_playbook",
            END: END,
        },
    )

    # Playbook resolution → assess risk (unconditional)
    graph.add_edge("resolve_playbook", "assess_risk")

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
