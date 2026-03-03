"""LangGraph workflow definition for the Zero Trust Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.tracing import traced_node
from shieldops.agents.zero_trust.models import ZeroTrustState
from shieldops.agents.zero_trust.nodes import (
    assess_device,
    enforce_policy,
    evaluate_access,
    finalize_assessment,
    verify_identity,
)


def should_assess_device(state: ZeroTrustState) -> str:
    """Check if device assessment is needed based on identity verification."""
    if state.error:
        return "finalize_assessment"
    if state.identity_verified > 0:
        return "assess_device"
    return "finalize_assessment"


def should_enforce(state: ZeroTrustState) -> str:
    """Check if policy enforcement is needed based on violations."""
    if state.violation_count > 0:
        return "enforce_policy"
    return "finalize_assessment"


def create_zero_trust_graph() -> StateGraph[ZeroTrustState]:
    """Build the Zero Trust Agent LangGraph workflow.

    Workflow:
        verify_identity -> [identity_verified? -> assess_device -> evaluate_access]
            -> [violations? -> enforce_policy]
            -> finalize_assessment
    """
    graph = StateGraph(ZeroTrustState)

    _agent = "zero_trust"
    graph.add_node(
        "verify_identity",
        traced_node("zero_trust.verify_identity", _agent)(verify_identity),
    )
    graph.add_node(
        "assess_device",
        traced_node("zero_trust.assess_device", _agent)(assess_device),
    )
    graph.add_node(
        "evaluate_access",
        traced_node("zero_trust.evaluate_access", _agent)(evaluate_access),
    )
    graph.add_node(
        "enforce_policy",
        traced_node("zero_trust.enforce_policy", _agent)(enforce_policy),
    )
    graph.add_node(
        "finalize_assessment",
        traced_node("zero_trust.finalize_assessment", _agent)(finalize_assessment),
    )

    # Define edges
    graph.set_entry_point("verify_identity")
    graph.add_conditional_edges(
        "verify_identity",
        should_assess_device,
        {"assess_device": "assess_device", "finalize_assessment": "finalize_assessment"},
    )
    graph.add_edge("assess_device", "evaluate_access")
    graph.add_conditional_edges(
        "evaluate_access",
        should_enforce,
        {"enforce_policy": "enforce_policy", "finalize_assessment": "finalize_assessment"},
    )
    graph.add_edge("enforce_policy", "finalize_assessment")
    graph.add_edge("finalize_assessment", END)

    return graph
