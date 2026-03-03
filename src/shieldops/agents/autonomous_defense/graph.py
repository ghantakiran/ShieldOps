"""LangGraph workflow definition for the AutonomousDefense Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.autonomous_defense.models import AutonomousDefenseState
from shieldops.agents.autonomous_defense.nodes import (
    assess_threats,
    deploy_countermeasures,
    finalize_defense,
    select_defenses,
    validate_protection,
)
from shieldops.agents.tracing import traced_node


def should_continue(state: AutonomousDefenseState) -> str:
    """Check if workflow should continue or finalize."""
    if state.error:
        return "finalize_defense"
    return "select_defenses"


def create_autonomous_defense_graph() -> StateGraph[AutonomousDefenseState]:
    """Build the AutonomousDefense Agent LangGraph workflow."""
    graph = StateGraph(AutonomousDefenseState)

    _agent = "autonomous_defense"
    graph.add_node(
        "assess_threats",
        traced_node("autonomous_defense.assess_threats", _agent)(assess_threats),
    )
    graph.add_node(
        "select_defenses",
        traced_node("autonomous_defense.select_defenses", _agent)(select_defenses),
    )
    graph.add_node(
        "deploy_countermeasures",
        traced_node("autonomous_defense.deploy_countermeasures", _agent)(deploy_countermeasures),
    )
    graph.add_node(
        "validate_protection",
        traced_node("autonomous_defense.validate_protection", _agent)(validate_protection),
    )
    graph.add_node(
        "finalize_defense",
        traced_node("autonomous_defense.finalize_defense", _agent)(finalize_defense),
    )

    graph.set_entry_point("assess_threats")
    graph.add_conditional_edges(
        "assess_threats",
        should_continue,
        {
            "select_defenses": "select_defenses",
            "finalize_defense": "finalize_defense",
        },
    )
    graph.add_edge("select_defenses", "deploy_countermeasures")
    graph.add_edge("deploy_countermeasures", "validate_protection")
    graph.add_edge("validate_protection", "finalize_defense")
    graph.add_edge("finalize_defense", END)

    return graph
