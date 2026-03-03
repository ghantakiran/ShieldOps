"""LangGraph workflow definition for the Threat Automation Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.threat_automation.models import ThreatAutomationState
from shieldops.agents.threat_automation.nodes import (
    analyze_behavior,
    automate_response,
    correlate_intelligence,
    detect_threats,
    finalize_hunt,
)
from shieldops.agents.tracing import traced_node


def should_analyze(state: ThreatAutomationState) -> str:
    """Check if behavior analysis is needed based on detection results."""
    if state.error:
        return "finalize_hunt"
    if state.threat_count > 0:
        return "analyze_behavior"
    return "finalize_hunt"


def should_respond(state: ThreatAutomationState) -> str:
    """Check if automated response is needed based on critical threat count."""
    if state.critical_count > 0:
        return "automate_response"
    return "finalize_hunt"


def create_threat_automation_graph() -> StateGraph[ThreatAutomationState]:
    """Build the Threat Automation Agent LangGraph workflow.

    Workflow:
        detect_threats -> [has_threats? -> analyze_behavior -> correlate_intelligence]
            -> [critical? -> automate_response]
            -> finalize_hunt
    """
    graph = StateGraph(ThreatAutomationState)

    _agent = "threat_automation"
    graph.add_node(
        "detect_threats",
        traced_node("threat_automation.detect_threats", _agent)(detect_threats),
    )
    graph.add_node(
        "analyze_behavior",
        traced_node("threat_automation.analyze_behavior", _agent)(analyze_behavior),
    )
    graph.add_node(
        "correlate_intelligence",
        traced_node("threat_automation.correlate_intelligence", _agent)(correlate_intelligence),
    )
    graph.add_node(
        "automate_response",
        traced_node("threat_automation.automate_response", _agent)(automate_response),
    )
    graph.add_node(
        "finalize_hunt",
        traced_node("threat_automation.finalize_hunt", _agent)(finalize_hunt),
    )

    # Define edges
    graph.set_entry_point("detect_threats")
    graph.add_conditional_edges(
        "detect_threats",
        should_analyze,
        {"analyze_behavior": "analyze_behavior", "finalize_hunt": "finalize_hunt"},
    )
    graph.add_edge("analyze_behavior", "correlate_intelligence")
    graph.add_conditional_edges(
        "correlate_intelligence",
        should_respond,
        {"automate_response": "automate_response", "finalize_hunt": "finalize_hunt"},
    )
    graph.add_edge("automate_response", "finalize_hunt")
    graph.add_edge("finalize_hunt", END)

    return graph
