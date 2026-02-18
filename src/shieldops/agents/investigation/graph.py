"""LangGraph workflow definition for the Investigation Agent."""

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from langgraph.graph import END, StateGraph

from shieldops.agents.investigation.models import InvestigationState, ReasoningStep
from shieldops.agents.investigation.nodes import (
    analyze_logs,
    analyze_metrics,
    analyze_traces,
    correlate_findings,
    gather_context,
    generate_hypotheses,
)
from shieldops.agents.investigation.prompts import (
    SYSTEM_RECOMMEND_ACTION,
    RecommendedActionOutput,
)
from shieldops.config import settings
from shieldops.models.base import Environment, RemediationAction, RiskLevel
from shieldops.utils.llm import llm_structured

logger = structlog.get_logger()


def should_analyze_traces(state: InvestigationState) -> str:
    """Decide if trace analysis is needed based on initial findings."""
    if state.error:
        return "generate_hypotheses"
    # Analyze traces if we found errors suggesting distributed issues
    has_distributed_errors = any(
        f.severity == "error" and "timeout" in f.summary.lower() for f in state.log_findings
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
    """Generate a remediation recommendation for high-confidence hypotheses using the LLM."""
    start = datetime.now(UTC)
    top_hypothesis = state.hypotheses[0] if state.hypotheses else None

    logger.info(
        "investigation_recommending_action",
        alert_id=state.alert_id,
        confidence=state.confidence_score,
        hypothesis=top_hypothesis.description[:100] if top_hypothesis else "none",
    )

    recommended = None
    output_summary = "No hypothesis available for action recommendation"

    if top_hypothesis:
        # Build context for the LLM
        context_lines = [
            "## Top Hypothesis",
            f"Description: {top_hypothesis.description}",
            f"Confidence: {top_hypothesis.confidence}",
            f"Evidence: {'; '.join(top_hypothesis.evidence[:5])}",
            f"Affected resources: {', '.join(top_hypothesis.affected_resources)}",
            f"Suggested action: {top_hypothesis.recommended_action or 'none'}",
            "",
            "## Alert Context",
            f"Alert: {state.alert_context.alert_name}",
            f"Severity: {state.alert_context.severity}",
            f"Resource: {state.alert_context.resource_id}",
            f"Environment: {state.alert_context.labels.get('environment', 'production')}",
        ]
        user_prompt = "\n".join(context_lines)

        try:
            result: RecommendedActionOutput = await llm_structured(
                system_prompt=SYSTEM_RECOMMEND_ACTION,
                user_prompt=user_prompt,
                schema=RecommendedActionOutput,
            )

            env_str = state.alert_context.labels.get("environment", "production")
            try:
                env = Environment(env_str)
            except ValueError:
                env = Environment.PRODUCTION

            try:
                risk = RiskLevel(result.risk_level)
            except ValueError:
                risk = RiskLevel.MEDIUM

            recommended = RemediationAction(
                id=f"act-{uuid4().hex[:12]}",
                action_type=result.action_type,
                target_resource=result.target_resource,
                environment=env,
                risk_level=risk,
                parameters=result.parameters,
                description=result.description,
                estimated_duration_seconds=result.estimated_duration_seconds,
                rollback_capable=risk != RiskLevel.CRITICAL,
            )

            output_summary = (
                f"Recommended: {result.action_type} on {result.target_resource} "
                f"(risk: {result.risk_level}, est: {result.estimated_duration_seconds}s)"
            )
        except Exception as e:
            logger.error("llm_recommend_action_failed", error=str(e))
            output_summary = f"Action recommendation failed: {e}"

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="recommend_action",
        input_summary=(
            f"Top hypothesis: {top_hypothesis.description[:100] if top_hypothesis else 'None'}"
        ),
        output_summary=output_summary,
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="llm",
    )

    return {
        "recommended_action": recommended,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
        "investigation_duration_ms": int(
            (datetime.now(UTC) - state.investigation_start).total_seconds() * 1000
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
