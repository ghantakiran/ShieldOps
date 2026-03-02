"""LangGraph workflow definition for the Threat Hunter Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.threat_hunter.models import ThreatHunterState
from shieldops.agents.threat_hunter.nodes import (
    analyze_behavior,
    assess_threat,
    check_mitre,
    collect_data,
    correlate_findings,
    define_scope,
    generate_hypothesis,
    recommend_response,
    sweep_iocs,
    track_effectiveness,
)
from shieldops.agents.tracing import traced_node


def should_recommend_response(state: ThreatHunterState) -> str:
    """Route to response recommendations if a threat was found."""
    if state.error:
        return "track_effectiveness"
    if state.threat_found:
        return "recommend_response"
    return "track_effectiveness"


def create_threat_hunter_graph() -> StateGraph[ThreatHunterState]:
    """Build the Threat Hunter Agent LangGraph workflow.

    Workflow:
        generate_hypothesis → define_scope → collect_data
            → sweep_iocs → analyze_behavior → check_mitre
            → correlate_findings → assess_threat
            → [found? → recommend_response]
            → track_effectiveness → END
    """
    graph = StateGraph(ThreatHunterState)

    _agent = "threat_hunter"
    graph.add_node(
        "generate_hypothesis",
        traced_node("threat_hunter.generate_hypothesis", _agent)(generate_hypothesis),
    )
    graph.add_node(
        "define_scope",
        traced_node("threat_hunter.define_scope", _agent)(define_scope),
    )
    graph.add_node(
        "collect_data",
        traced_node("threat_hunter.collect_data", _agent)(collect_data),
    )
    graph.add_node(
        "sweep_iocs",
        traced_node("threat_hunter.sweep_iocs", _agent)(sweep_iocs),
    )
    graph.add_node(
        "analyze_behavior",
        traced_node("threat_hunter.analyze_behavior", _agent)(analyze_behavior),
    )
    graph.add_node(
        "check_mitre",
        traced_node("threat_hunter.check_mitre", _agent)(check_mitre),
    )
    graph.add_node(
        "correlate_findings",
        traced_node("threat_hunter.correlate_findings", _agent)(correlate_findings),
    )
    graph.add_node(
        "assess_threat",
        traced_node("threat_hunter.assess_threat", _agent)(assess_threat),
    )
    graph.add_node(
        "recommend_response",
        traced_node("threat_hunter.recommend_response", _agent)(recommend_response),
    )
    graph.add_node(
        "track_effectiveness",
        traced_node("threat_hunter.track_effectiveness", _agent)(track_effectiveness),
    )

    # Define edges
    graph.set_entry_point("generate_hypothesis")
    graph.add_edge("generate_hypothesis", "define_scope")
    graph.add_edge("define_scope", "collect_data")
    graph.add_edge("collect_data", "sweep_iocs")
    graph.add_edge("sweep_iocs", "analyze_behavior")
    graph.add_edge("analyze_behavior", "check_mitre")
    graph.add_edge("check_mitre", "correlate_findings")
    graph.add_edge("correlate_findings", "assess_threat")
    graph.add_conditional_edges(
        "assess_threat",
        should_recommend_response,
        {
            "recommend_response": "recommend_response",
            "track_effectiveness": "track_effectiveness",
        },
    )
    graph.add_edge("recommend_response", "track_effectiveness")
    graph.add_edge("track_effectiveness", END)

    return graph
