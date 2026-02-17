"""LangGraph workflow definition for the Investigation Agent."""

from datetime import datetime, timezone

import structlog
from langgraph.graph import END, StateGraph

from shieldops.agents.investigation.models import InvestigationState, ReasoningStep
from shieldops.agents.investigation.nodes import (
    analyze_logs,
    analyze_metrics,
    analyze_traces,
    correlate_findings,
    generate_hypotheses,
    gather_context,
)
from shieldops.config import settings

logger = structlog.get_logger()


def should_analyze_traces(state: InvestigationState) -> str:
    """Decide if trace analysis is needed based on initial findings."""
    if state.error:
        return "generate_hypotheses"
    # Analyze traces if we found errors suggesting distributed issues
    has_distributed_errors = any(
        f.severity == "error" and "timeout" in f.summary.lower()
        for f in state.log_findings
    )
    if has_distributed_errors:
        return "analyze_traces"
    return "correlate_findings"


def should_recommend_action(state: InvestigationState) -> str:
    """Route based on confidence score."""
    if state.confidence_score >= settings.agent_confidence_threshold_auto:
        return "recommend_action"
    return END


async def recommend_action(state: InvestigationState) -> dict:
    """Generate a remediation recommendation for high-confidence hypotheses."""
    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="recommend_action",
        input_summary=f"Top hypothesis: {state.hypotheses[0].description if state.hypotheses else 'None'}",
        output_summary="Generated remediation recommendation",
        duration_ms=0,
        tool_used="llm",
    )

    logger.info(
        "investigation_recommending_action",
        alert_id=state.alert_id,
        confidence=state.confidence_score,
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
        "investigation_duration_ms": int(
            (datetime.now(timezone.utc) - state.investigation_start).total_seconds() * 1000
        )
        if state.investigation_start
        else 0,
    }


def create_investigation_graph() -> StateGraph:
    """Build the Investigation Agent LangGraph workflow.

    Workflow:
        gather_context → analyze_logs → analyze_metrics
            → [conditional: analyze_traces OR correlate_findings]
            → generate_hypotheses
            → [conditional: recommend_action OR end]
    """
    graph = StateGraph(InvestigationState)

    # Add nodes
    graph.add_node("gather_context", gather_context)
    graph.add_node("analyze_logs", analyze_logs)
    graph.add_node("analyze_metrics", analyze_metrics)
    graph.add_node("analyze_traces", analyze_traces)
    graph.add_node("correlate_findings", correlate_findings)
    graph.add_node("generate_hypotheses", generate_hypotheses)
    graph.add_node("recommend_action", recommend_action)

    # Define edges
    graph.set_entry_point("gather_context")
    graph.add_edge("gather_context", "analyze_logs")
    graph.add_edge("analyze_logs", "analyze_metrics")
    graph.add_conditional_edges(
        "analyze_metrics",
        should_analyze_traces,
        {
            "analyze_traces": "analyze_traces",
            "correlate_findings": "correlate_findings",
            "generate_hypotheses": "generate_hypotheses",
        },
    )
    graph.add_edge("analyze_traces", "correlate_findings")
    graph.add_edge("correlate_findings", "generate_hypotheses")
    graph.add_conditional_edges(
        "generate_hypotheses",
        should_recommend_action,
        {
            "recommend_action": "recommend_action",
            END: END,
        },
    )
    graph.add_edge("recommend_action", END)

    return graph
