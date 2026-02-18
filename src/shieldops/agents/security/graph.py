"""LangGraph workflow definition for the Security Agent.

Workflow:
    scan_vulnerabilities → assess_findings
    → [if not cve_only] check_credentials
    → [if not cve_only/credentials_only] evaluate_compliance
    → synthesize_posture → END
"""

import structlog
from langgraph.graph import END, StateGraph

from shieldops.agents.security.models import SecurityScanState
from shieldops.agents.security.nodes import (
    assess_findings,
    check_credentials,
    evaluate_compliance,
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


def create_security_graph() -> StateGraph:
    """Build the Security Agent LangGraph workflow."""
    graph = StateGraph(SecurityScanState)

    # Add nodes
    graph.add_node("scan_vulnerabilities", scan_vulnerabilities)
    graph.add_node("assess_findings", assess_findings)
    graph.add_node("check_credentials", check_credentials)
    graph.add_node("evaluate_compliance", evaluate_compliance)
    graph.add_node("synthesize_posture", synthesize_posture)

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

    # Posture → END
    graph.add_edge("synthesize_posture", END)

    return graph
