"""LangGraph workflow definition for the Forensics Agent."""

from langgraph.graph import END, StateGraph

from shieldops.agents.forensics.models import ForensicsState
from shieldops.agents.forensics.nodes import (
    analyze_disk,
    analyze_memory,
    analyze_network,
    collect_artifacts,
    extract_iocs,
    generate_report,
    preserve_evidence,
    reconstruct_timeline,
    synthesize,
    verify_integrity,
)
from shieldops.agents.tracing import traced_node


def should_continue_after_integrity(state: ForensicsState) -> str:
    """Check if evidence integrity is valid before proceeding."""
    if state.error:
        return "generate_report"
    if not state.integrity_verified:
        return "generate_report"
    return "collect_artifacts"


def create_forensics_graph() -> StateGraph[ForensicsState]:
    """Build the Forensics Agent LangGraph workflow.

    Workflow:
        preserve_evidence → verify_integrity
            → [integrity_ok? → collect_artifacts]
            → [analyze_memory, analyze_disk, analyze_network]
            → reconstruct_timeline → extract_iocs
            → synthesize → generate_report → END
    """
    graph = StateGraph(ForensicsState)

    _agent = "forensics"
    graph.add_node(
        "preserve_evidence",
        traced_node("forensics.preserve_evidence", _agent)(preserve_evidence),
    )
    graph.add_node(
        "verify_integrity",
        traced_node("forensics.verify_integrity", _agent)(verify_integrity),
    )
    graph.add_node(
        "collect_artifacts",
        traced_node("forensics.collect_artifacts", _agent)(collect_artifacts),
    )
    graph.add_node(
        "analyze_memory",
        traced_node("forensics.analyze_memory", _agent)(analyze_memory),
    )
    graph.add_node(
        "analyze_disk",
        traced_node("forensics.analyze_disk", _agent)(analyze_disk),
    )
    graph.add_node(
        "analyze_network",
        traced_node("forensics.analyze_network", _agent)(analyze_network),
    )
    graph.add_node(
        "reconstruct_timeline",
        traced_node("forensics.reconstruct_timeline", _agent)(reconstruct_timeline),
    )
    graph.add_node(
        "extract_iocs",
        traced_node("forensics.extract_iocs", _agent)(extract_iocs),
    )
    graph.add_node(
        "synthesize",
        traced_node("forensics.synthesize", _agent)(synthesize),
    )
    graph.add_node(
        "generate_report",
        traced_node("forensics.generate_report", _agent)(generate_report),
    )

    # Define edges
    graph.set_entry_point("preserve_evidence")
    graph.add_edge("preserve_evidence", "verify_integrity")
    graph.add_conditional_edges(
        "verify_integrity",
        should_continue_after_integrity,
        {
            "collect_artifacts": "collect_artifacts",
            "generate_report": "generate_report",
        },
    )
    graph.add_edge("collect_artifacts", "analyze_memory")
    graph.add_edge("analyze_memory", "analyze_disk")
    graph.add_edge("analyze_disk", "analyze_network")
    graph.add_edge("analyze_network", "reconstruct_timeline")
    graph.add_edge("reconstruct_timeline", "extract_iocs")
    graph.add_edge("extract_iocs", "synthesize")
    graph.add_edge("synthesize", "generate_report")
    graph.add_edge("generate_report", END)

    return graph
