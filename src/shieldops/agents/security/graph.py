"""LangGraph workflow definition for the Security Agent.

Workflow:
    scan_vulnerabilities → assess_findings
    → [if not cve_only] check_credentials
    → [if not cve_only/credentials_only] evaluate_compliance
    → synthesize_posture
    → [if persist_findings] persist_findings
    → [if execute_actions] evaluate_action_policy
      → [if policy allowed] execute_patches
      → [if rotations needed] rotate_credentials
    → END

Extended scan types (container, git_secrets, iac, network, k8s_security)
route through their dedicated scanner node → assess → posture → persist → END.
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
    persist_findings,
    rotate_credentials,
    scan_containers,
    scan_iac,
    scan_k8s_security,
    scan_network,
    scan_secrets,
    scan_vulnerabilities,
    synthesize_posture,
)

logger = structlog.get_logger()

# Extended scan types that use dedicated scanner nodes
EXTENDED_SCAN_TYPES = {
    "container",
    "git_secrets",
    "git_deps",
    "iac",
    "network",
    "k8s_security",
}


def route_scan_type(state: SecurityScanState) -> str:
    """Route to the appropriate scanner node based on scan_type."""
    if state.scan_type == "container":
        return "scan_containers"
    if state.scan_type in ("git_secrets", "git_deps"):
        return "scan_secrets"
    if state.scan_type == "iac":
        return "scan_iac"
    if state.scan_type == "network":
        return "scan_network"
    if state.scan_type == "k8s_security":
        return "scan_k8s_security"
    # Default: standard CVE/full scan
    return "scan_vulnerabilities"


def should_check_credentials(state: SecurityScanState) -> str:
    """Skip credential check if scan type is cve_only or extended."""
    if state.scan_type in ("cve_only", *EXTENDED_SCAN_TYPES):
        return "synthesize_posture"
    if state.error:
        return "synthesize_posture"
    return "check_credentials"


def should_evaluate_compliance(state: SecurityScanState) -> str:
    """Skip compliance if scan type is cve_only or credentials_only."""
    if state.scan_type in ("cve_only", "credentials_only", *EXTENDED_SCAN_TYPES):
        return "synthesize_posture"
    if state.error:
        return "synthesize_posture"
    return "evaluate_compliance"


def should_persist(state: SecurityScanState) -> str:
    """Persist findings to lifecycle DB if enabled."""
    if not state.persist_findings:
        return "check_execute_actions"
    return "persist_findings"


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


def route_extended_post_scan(state: SecurityScanState) -> str:
    """After extended scanner, go to assess_findings then posture."""
    return "assess_findings"


def create_security_graph() -> StateGraph[SecurityScanState]:
    """Build the Security Agent LangGraph workflow."""
    graph = StateGraph(SecurityScanState)

    # Add all nodes
    graph.add_node("scan_vulnerabilities", scan_vulnerabilities)
    graph.add_node("scan_containers", scan_containers)
    graph.add_node("scan_secrets", scan_secrets)
    graph.add_node("scan_iac", scan_iac)
    graph.add_node("scan_network", scan_network)
    graph.add_node("scan_k8s_security", scan_k8s_security)
    graph.add_node("assess_findings", assess_findings)
    graph.add_node("check_credentials", check_credentials)
    graph.add_node("evaluate_compliance", evaluate_compliance)
    graph.add_node("synthesize_posture", synthesize_posture)
    graph.add_node("persist_findings", persist_findings)
    graph.add_node("evaluate_action_policy", evaluate_action_policy)
    graph.add_node("execute_patches", execute_patches)
    graph.add_node("rotate_credentials", rotate_credentials)

    # Entry: route based on scan_type
    graph.set_conditional_entry_point(
        route_scan_type,
        {
            "scan_vulnerabilities": "scan_vulnerabilities",
            "scan_containers": "scan_containers",
            "scan_secrets": "scan_secrets",
            "scan_iac": "scan_iac",
            "scan_network": "scan_network",
            "scan_k8s_security": "scan_k8s_security",
        },
    )

    # Standard scan: scan_vuln → assess
    graph.add_edge("scan_vulnerabilities", "assess_findings")

    # Extended scanners → assess_findings
    graph.add_edge("scan_containers", "assess_findings")
    graph.add_edge("scan_secrets", "assess_findings")
    graph.add_edge("scan_iac", "assess_findings")
    graph.add_edge("scan_network", "assess_findings")
    graph.add_edge("scan_k8s_security", "assess_findings")

    # assess → check_credentials or skip to posture
    graph.add_conditional_edges(
        "assess_findings",
        should_check_credentials,
        {
            "check_credentials": "check_credentials",
            "synthesize_posture": "synthesize_posture",
        },
    )

    # credentials → compliance or skip to posture
    graph.add_conditional_edges(
        "check_credentials",
        should_evaluate_compliance,
        {
            "evaluate_compliance": "evaluate_compliance",
            "synthesize_posture": "synthesize_posture",
        },
    )

    # compliance → posture
    graph.add_edge("evaluate_compliance", "synthesize_posture")

    # posture → persist or check actions
    graph.add_conditional_edges(
        "synthesize_posture",
        should_persist,
        {
            "persist_findings": "persist_findings",
            "check_execute_actions": "check_execute_actions",
        },
    )

    # persist → check actions
    # We use a pass-through node name mapped to the conditional check
    graph.add_node(
        "check_execute_actions",
        lambda state: {"current_step": "complete"},
    )
    graph.add_edge("persist_findings", "check_execute_actions")

    # check_execute_actions → action phase or END
    graph.add_conditional_edges(
        "check_execute_actions",
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

    # Patches → rotate or END
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
