"""LangGraph workflow definition for the Security Agent.

Workflow:
    scan_vulnerabilities → assess_findings
    → [if not cve_only] check_credentials
    → [if not cve_only/credentials_only] evaluate_compliance
    → synthesize_posture
    → [if execute_actions] evaluate_action_policy
      → [if policy allowed] execute_patches
      → [if rotations needed] rotate_credentials
    → END
"""

import structlog
from langgraph.graph import END, StateGraph

from shieldops.agents.security.models import SecurityScanState
from shieldops.agents.security.nodes import (
    assess_findings,
    check_credentials,
    evaluate_action_policy,
    evaluate_compliance,
    execute_patches,
    rotate_credentials,
    scan_vulnerabilities,
    synthesize_posture,
)

logger = structlog.get_logger()


def should_check_credentials(state: SecurityScanState) -> str:
    """Skip credential check if scan type is cve_only."""
    if state.scan_type == "cve_only":
        return "synthesize_posture"
    if state.error:
        return "synthesize_posture"
    return "check_credentials"


def should_evaluate_compliance(state: SecurityScanState) -> str:
    """Skip compliance if scan type is cve_only or credentials_only."""
    if state.scan_type in ("cve_only", "credentials_only"):
        return "synthesize_posture"
    if state.error:
        return "synthesize_posture"
    return "evaluate_compliance"


def should_execute_actions(state: SecurityScanState) -> str:
    """Only enter the action phase if execute_actions is True."""
    if not state.execute_actions:
        return END
    if state.error:
        return END
    return "evaluate_action_policy"


def action_policy_gate(state: SecurityScanState) -> str:
    """Stop action execution if policy denied."""
    if state.action_policy_result and not state.action_policy_result.allowed:
        return END
    return "execute_patches"


def should_rotate_after_patches(state: SecurityScanState) -> str:
    """Skip credential rotation if none need rotating."""
    if not any(c.needs_rotation for c in state.credential_statuses):
        return END
    return "rotate_credentials"


def create_security_graph() -> StateGraph:
    """Build the Security Agent LangGraph workflow."""
    graph = StateGraph(SecurityScanState)

    # Add nodes
    graph.add_node("scan_vulnerabilities", scan_vulnerabilities)
    graph.add_node("assess_findings", assess_findings)
    graph.add_node("check_credentials", check_credentials)
    graph.add_node("evaluate_compliance", evaluate_compliance)
    graph.add_node("synthesize_posture", synthesize_posture)
    graph.add_node("evaluate_action_policy", evaluate_action_policy)
    graph.add_node("execute_patches", execute_patches)
    graph.add_node("rotate_credentials", rotate_credentials)

    # Entry point
    graph.set_entry_point("scan_vulnerabilities")

    # Linear: scan → assess
    graph.add_edge("scan_vulnerabilities", "assess_findings")

    # Conditional: assess → credentials or skip to posture
    graph.add_conditional_edges(
        "assess_findings",
        should_check_credentials,
        {
            "check_credentials": "check_credentials",
            "synthesize_posture": "synthesize_posture",
        },
    )

    # Conditional: credentials → compliance or skip to posture
    graph.add_conditional_edges(
        "check_credentials",
        should_evaluate_compliance,
        {
            "evaluate_compliance": "evaluate_compliance",
            "synthesize_posture": "synthesize_posture",
        },
    )

    # Compliance → posture
    graph.add_edge("evaluate_compliance", "synthesize_posture")

    # Posture → action phase (opt-in) or END
    graph.add_conditional_edges(
        "synthesize_posture",
        should_execute_actions,
        {
            "evaluate_action_policy": "evaluate_action_policy",
            END: END,
        },
    )

    # Policy gate → patches or END
    graph.add_conditional_edges(
        "evaluate_action_policy",
        action_policy_gate,
        {
            "execute_patches": "execute_patches",
            END: END,
        },
    )

    # Patches → rotate credentials or END
    graph.add_conditional_edges(
        "execute_patches",
        should_rotate_after_patches,
        {
            "rotate_credentials": "rotate_credentials",
            END: END,
        },
    )

    # Rotate → END
    graph.add_edge("rotate_credentials", END)

    return graph
