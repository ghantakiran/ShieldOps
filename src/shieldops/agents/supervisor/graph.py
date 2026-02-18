"""LangGraph workflow definition for the Supervisor Agent.

Workflow:
    classify_event → dispatch_to_agent → evaluate_result
    → [should_chain?] chain_followup
    → [needs_escalation?] escalate
    → finalize → END
"""

import structlog
from langgraph.graph import END, StateGraph

from shieldops.agents.supervisor.models import SupervisorState
from shieldops.agents.supervisor.nodes import (
    chain_followup,
    classify_event,
    dispatch_to_agent,
    escalate,
    evaluate_result,
    finalize,
)

logger = structlog.get_logger()


def should_chain_or_escalate(state: SupervisorState) -> str:
    """After evaluating result, decide whether to chain, escalate, or finalize."""
    if state.error:
        return "finalize"
    if state.should_chain:
        return "chain_followup"
    if state.needs_escalation:
        return "escalate"
    return "finalize"


def after_chain(state: SupervisorState) -> str:
    """After chaining, check if escalation is also needed."""
    if state.needs_escalation:
        return "escalate"
    return "finalize"


def create_supervisor_graph() -> StateGraph:
    """Build the Supervisor Agent LangGraph workflow."""
    graph = StateGraph(SupervisorState)

    # Add nodes
    graph.add_node("classify_event", classify_event)
    graph.add_node("dispatch_to_agent", dispatch_to_agent)
    graph.add_node("evaluate_result", evaluate_result)
    graph.add_node("chain_followup", chain_followup)
    graph.add_node("escalate", escalate)
    graph.add_node("finalize", finalize)

    # Entry point
    graph.set_entry_point("classify_event")

    # Linear: classify → dispatch → evaluate
    graph.add_edge("classify_event", "dispatch_to_agent")
    graph.add_edge("dispatch_to_agent", "evaluate_result")

    # Conditional: evaluate → chain, escalate, or finalize
    graph.add_conditional_edges(
        "evaluate_result",
        should_chain_or_escalate,
        {
            "chain_followup": "chain_followup",
            "escalate": "escalate",
            "finalize": "finalize",
        },
    )

    # Conditional: after chain → escalate or finalize
    graph.add_conditional_edges(
        "chain_followup",
        after_chain,
        {
            "escalate": "escalate",
            "finalize": "finalize",
        },
    )

    # Escalate → finalize
    graph.add_edge("escalate", "finalize")

    # Finalize → END
    graph.add_edge("finalize", END)

    return graph
