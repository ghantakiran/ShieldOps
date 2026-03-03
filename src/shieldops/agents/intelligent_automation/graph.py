"""LangGraph workflow definition for the IntelligentAutomation Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.intelligent_automation.models import IntelligentAutomationState
from shieldops.agents.intelligent_automation.nodes import (
    assess_situation,
    execute_automation,
    finalize_execution,
    select_strategy,
    validate_outcome,
)
from shieldops.agents.tracing import traced_node


def should_continue(state: IntelligentAutomationState) -> str:
    """Check if workflow should continue or finalize."""
    if state.error:
        return "finalize_execution"
    return "select_strategy"


def create_intelligent_automation_graph() -> StateGraph[IntelligentAutomationState]:
    """Build the IntelligentAutomation Agent LangGraph workflow."""
    graph = StateGraph(IntelligentAutomationState)

    _agent = "intelligent_automation"
    graph.add_node(
        "assess_situation",
        traced_node("intelligent_automation.assess_situation", _agent)(assess_situation),
    )
    graph.add_node(
        "select_strategy",
        traced_node("intelligent_automation.select_strategy", _agent)(select_strategy),
    )
    graph.add_node(
        "execute_automation",
        traced_node("intelligent_automation.execute_automation", _agent)(execute_automation),
    )
    graph.add_node(
        "validate_outcome",
        traced_node("intelligent_automation.validate_outcome", _agent)(validate_outcome),
    )
    graph.add_node(
        "finalize_execution",
        traced_node("intelligent_automation.finalize_execution", _agent)(finalize_execution),
    )

    graph.set_entry_point("assess_situation")
    graph.add_conditional_edges(
        "assess_situation",
        should_continue,
        {"select_strategy": "select_strategy", "finalize_execution": "finalize_execution"},
    )
    graph.add_edge("select_strategy", "execute_automation")
    graph.add_edge("execute_automation", "validate_outcome")
    graph.add_edge("validate_outcome", "finalize_execution")
    graph.add_edge("finalize_execution", END)

    return graph
