"""LangGraph workflow definition for the Deception Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.deception.models import DeceptionState
from shieldops.agents.deception.nodes import (
    analyze_behavior,
    deploy_assets,
    extract_indicators,
    generate_report,
    monitor_interactions,
    respond_to_threat,
    update_strategy,
)
from shieldops.agents.tracing import traced_node


def should_analyze(state: DeceptionState) -> str:
    """Route based on whether interactions were detected."""
    if state.error:
        return "generate_report"
    if state.interaction_detected:
        return "analyze_behavior"
    return "generate_report"


def should_respond(state: DeceptionState) -> str:
    """Route based on severity level."""
    if state.severity_level in ("critical", "high"):
        return "respond_to_threat"
    return "update_strategy"


def create_deception_graph() -> StateGraph[DeceptionState]:
    """Build the Deception Agent LangGraph workflow.

    Workflow:
        deploy_assets -> monitor_interactions
            -> [interaction_detected? -> analyze_behavior -> extract_indicators]
            -> [high severity? -> respond_to_threat]
            -> update_strategy -> generate_report -> END
    """
    graph = StateGraph(DeceptionState)

    _agent = "deception"
    graph.add_node(
        "deploy_assets",
        traced_node("deception.deploy_assets", _agent)(deploy_assets),
    )
    graph.add_node(
        "monitor_interactions",
        traced_node("deception.monitor_interactions", _agent)(monitor_interactions),
    )
    graph.add_node(
        "analyze_behavior",
        traced_node("deception.analyze_behavior", _agent)(analyze_behavior),
    )
    graph.add_node(
        "extract_indicators",
        traced_node("deception.extract_indicators", _agent)(extract_indicators),
    )
    graph.add_node(
        "respond_to_threat",
        traced_node("deception.respond_to_threat", _agent)(respond_to_threat),
    )
    graph.add_node(
        "update_strategy",
        traced_node("deception.update_strategy", _agent)(update_strategy),
    )
    graph.add_node(
        "generate_report",
        traced_node("deception.generate_report", _agent)(generate_report),
    )

    # Define edges
    graph.set_entry_point("deploy_assets")
    graph.add_edge("deploy_assets", "monitor_interactions")
    graph.add_conditional_edges(
        "monitor_interactions",
        should_analyze,
        {
            "analyze_behavior": "analyze_behavior",
            "generate_report": "generate_report",
        },
    )
    graph.add_edge("analyze_behavior", "extract_indicators")
    graph.add_conditional_edges(
        "extract_indicators",
        should_respond,
        {
            "respond_to_threat": "respond_to_threat",
            "update_strategy": "update_strategy",
        },
    )
    graph.add_edge("respond_to_threat", "update_strategy")
    graph.add_edge("update_strategy", "generate_report")
    graph.add_edge("generate_report", END)

    return graph
