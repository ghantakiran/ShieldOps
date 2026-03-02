"""LangGraph workflow definition for the Incident Response Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.incident_response.models import IncidentResponseState
from shieldops.agents.incident_response.nodes import (
    assess_incident,
    execute_containment,
    finalize_response,
    plan_containment,
    plan_eradication,
    plan_recovery,
    validate_response,
)
from shieldops.agents.tracing import traced_node


def should_contain(state: IncidentResponseState) -> str:
    """Check if containment is needed based on severity."""
    if state.error:
        return "finalize_response"
    if state.assessment_score >= 50:
        return "plan_containment"
    return "plan_recovery"


def should_validate(state: IncidentResponseState) -> str:
    """Check if recovery validation is needed."""
    if state.recovery_tasks:
        return "validate_response"
    return "finalize_response"


def create_incident_response_graph() -> StateGraph[IncidentResponseState]:
    """Build the Incident Response Agent LangGraph workflow.

    Workflow:
        assess_incident -> [severity>=50? -> plan_containment -> execute_containment]
            -> plan_eradication -> plan_recovery
            -> [has_tasks? -> validate_response]
            -> finalize_response
    """
    graph = StateGraph(IncidentResponseState)

    _agent = "incident_response"
    graph.add_node(
        "assess_incident",
        traced_node("incident_response.assess_incident", _agent)(assess_incident),
    )
    graph.add_node(
        "plan_containment",
        traced_node("incident_response.plan_containment", _agent)(plan_containment),
    )
    graph.add_node(
        "execute_containment",
        traced_node("incident_response.execute_containment", _agent)(execute_containment),
    )
    graph.add_node(
        "plan_eradication",
        traced_node("incident_response.plan_eradication", _agent)(plan_eradication),
    )
    graph.add_node(
        "plan_recovery",
        traced_node("incident_response.plan_recovery", _agent)(plan_recovery),
    )
    graph.add_node(
        "validate_response",
        traced_node("incident_response.validate_response", _agent)(validate_response),
    )
    graph.add_node(
        "finalize_response",
        traced_node("incident_response.finalize_response", _agent)(finalize_response),
    )

    # Define edges
    graph.set_entry_point("assess_incident")
    graph.add_conditional_edges(
        "assess_incident",
        should_contain,
        {
            "plan_containment": "plan_containment",
            "plan_recovery": "plan_recovery",
            "finalize_response": "finalize_response",
        },
    )
    graph.add_edge("plan_containment", "execute_containment")
    graph.add_edge("execute_containment", "plan_eradication")
    graph.add_edge("plan_eradication", "plan_recovery")
    graph.add_conditional_edges(
        "plan_recovery",
        should_validate,
        {"validate_response": "validate_response", "finalize_response": "finalize_response"},
    )
    graph.add_edge("validate_response", "finalize_response")
    graph.add_edge("finalize_response", END)

    return graph
