"""LangGraph workflow definition for the SOC Analyst Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.soc_analyst.models import SOCAnalystState
from shieldops.agents.soc_analyst.nodes import (
    correlate_events,
    enrich_alert,
    execute_playbook,
    finalize,
    generate_narrative,
    map_attack_chain,
    recommend_containment,
    triage_alert,
)
from shieldops.agents.tracing import traced_node


def should_suppress(state: SOCAnalystState) -> str:
    """Check if alert should be suppressed after triage."""
    if state.should_suppress:
        return END
    return "enrich_alert"


def should_map_attack_chain(state: SOCAnalystState) -> str:
    """Route Tier 2+ alerts to attack chain mapping."""
    if state.error:
        return "finalize"
    if state.tier >= 2:
        return "map_attack_chain"
    return "recommend_containment"


def should_auto_execute(state: SOCAnalystState) -> str:
    """Check if containment can be auto-executed."""
    auto_actions = [r for r in state.containment_recommendations if r.automated]
    if auto_actions:
        return "execute_playbook"
    return "finalize"


def create_soc_analyst_graph() -> StateGraph[SOCAnalystState]:
    """Build the SOC Analyst Agent LangGraph workflow.

    Workflow:
        triage_alert → [suppress? → END]
            → enrich_alert → correlate_events
            → [tier>=2? → map_attack_chain → generate_narrative]
            → recommend_containment
            → [auto-execute? → execute_playbook]
            → finalize
    """
    graph = StateGraph(SOCAnalystState)

    _agent = "soc_analyst"
    graph.add_node(
        "triage_alert",
        traced_node("soc_analyst.triage_alert", _agent)(triage_alert),
    )
    graph.add_node(
        "enrich_alert",
        traced_node("soc_analyst.enrich_alert", _agent)(enrich_alert),
    )
    graph.add_node(
        "correlate_events",
        traced_node("soc_analyst.correlate_events", _agent)(correlate_events),
    )
    graph.add_node(
        "map_attack_chain",
        traced_node("soc_analyst.map_attack_chain", _agent)(map_attack_chain),
    )
    graph.add_node(
        "generate_narrative",
        traced_node("soc_analyst.generate_narrative", _agent)(generate_narrative),
    )
    graph.add_node(
        "recommend_containment",
        traced_node("soc_analyst.recommend_containment", _agent)(recommend_containment),
    )
    graph.add_node(
        "execute_playbook",
        traced_node("soc_analyst.execute_playbook", _agent)(execute_playbook),
    )
    graph.add_node(
        "finalize",
        traced_node("soc_analyst.finalize", _agent)(finalize),
    )

    # Define edges
    graph.set_entry_point("triage_alert")
    graph.add_conditional_edges(
        "triage_alert",
        should_suppress,
        {"enrich_alert": "enrich_alert", END: END},
    )
    graph.add_edge("enrich_alert", "correlate_events")
    graph.add_conditional_edges(
        "correlate_events",
        should_map_attack_chain,
        {
            "map_attack_chain": "map_attack_chain",
            "recommend_containment": "recommend_containment",
            "finalize": "finalize",
        },
    )
    graph.add_edge("map_attack_chain", "generate_narrative")
    graph.add_edge("generate_narrative", "recommend_containment")
    graph.add_conditional_edges(
        "recommend_containment",
        should_auto_execute,
        {"execute_playbook": "execute_playbook", "finalize": "finalize"},
    )
    graph.add_edge("execute_playbook", "finalize")
    graph.add_edge("finalize", END)

    return graph
