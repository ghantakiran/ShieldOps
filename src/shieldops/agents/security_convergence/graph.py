"""LangGraph workflow definition for the SecurityConvergence Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.security_convergence.models import SecurityConvergenceState
from shieldops.agents.security_convergence.nodes import (
    collect_posture,
    coordinate_response,
    evaluate_defense,
    finalize_evaluation,
    unify_signals,
)
from shieldops.agents.tracing import traced_node


def should_continue(state: SecurityConvergenceState) -> str:
    """Check if workflow should continue or finalize."""
    if state.error:
        return "finalize_evaluation"
    return "unify_signals"


def create_security_convergence_graph() -> StateGraph[SecurityConvergenceState]:
    """Build the SecurityConvergence Agent LangGraph workflow."""
    graph = StateGraph(SecurityConvergenceState)

    _agent = "security_convergence"
    graph.add_node(
        "collect_posture",
        traced_node("security_convergence.collect_posture", _agent)(collect_posture),
    )
    graph.add_node(
        "unify_signals",
        traced_node("security_convergence.unify_signals", _agent)(unify_signals),
    )
    graph.add_node(
        "evaluate_defense",
        traced_node("security_convergence.evaluate_defense", _agent)(evaluate_defense),
    )
    graph.add_node(
        "coordinate_response",
        traced_node("security_convergence.coordinate_response", _agent)(coordinate_response),
    )
    graph.add_node(
        "finalize_evaluation",
        traced_node("security_convergence.finalize_evaluation", _agent)(finalize_evaluation),
    )

    graph.set_entry_point("collect_posture")
    graph.add_conditional_edges(
        "collect_posture",
        should_continue,
        {
            "unify_signals": "unify_signals",
            "finalize_evaluation": "finalize_evaluation",
        },
    )
    graph.add_edge("unify_signals", "evaluate_defense")
    graph.add_edge("evaluate_defense", "coordinate_response")
    graph.add_edge("coordinate_response", "finalize_evaluation")
    graph.add_edge("finalize_evaluation", END)

    return graph
