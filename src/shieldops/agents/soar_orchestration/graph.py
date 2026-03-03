"""LangGraph workflow definition for the Soar Orchestration Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.soar_orchestration.models import SOAROrchestrationState
from shieldops.agents.soar_orchestration.nodes import (
    execute_actions,
    finalize_orchestration,
    select_playbook,
    triage_incident,
    validate_response,
)
from shieldops.agents.tracing import traced_node


def should_continue(state: SOAROrchestrationState) -> str:
    """Check if workflow should continue or finalize."""
    if state.error:
        return "finalize_orchestration"
    return "select_playbook"


def create_soar_orchestration_graph() -> StateGraph[SOAROrchestrationState]:
    """Build the Soar Orchestration Agent LangGraph workflow."""
    graph = StateGraph(SOAROrchestrationState)

    _agent = "soar_orchestration"
    graph.add_node(
        "triage_incident",
        traced_node("soar_orchestration.triage_incident", _agent)(triage_incident),
    )
    graph.add_node(
        "select_playbook",
        traced_node("soar_orchestration.select_playbook", _agent)(select_playbook),
    )
    graph.add_node(
        "execute_actions",
        traced_node("soar_orchestration.execute_actions", _agent)(execute_actions),
    )
    graph.add_node(
        "validate_response",
        traced_node("soar_orchestration.validate_response", _agent)(validate_response),
    )
    graph.add_node(
        "finalize_orchestration",
        traced_node("soar_orchestration.finalize_orchestration", _agent)(finalize_orchestration),
    )

    graph.set_entry_point("triage_incident")
    graph.add_conditional_edges(
        "triage_incident",
        should_continue,
        {"select_playbook": "select_playbook", "finalize_orchestration": "finalize_orchestration"},
    )
    graph.add_edge("select_playbook", "execute_actions")
    graph.add_edge("execute_actions", "validate_response")
    graph.add_edge("validate_response", "finalize_orchestration")
    graph.add_edge("finalize_orchestration", END)

    return graph
