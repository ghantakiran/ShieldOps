"""Node implementations for the Investigation Agent LangGraph workflow.

Each node is an async function that:
1. Queries external systems via the InvestigationToolkit
2. Uses the LLM to analyze and reason about the data
3. Updates the investigation state with findings
4. Records its reasoning step in the audit trail
"""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.investigation.models import (
    CorrelatedEvent,
    InvestigationState,
    LogFinding,
    MetricAnomaly,
    ReasoningStep,
    TraceResult,
)
from shieldops.agents.investigation.prompts import (
    SYSTEM_CORRELATION,
    SYSTEM_HYPOTHESIS_GENERATION,
    SYSTEM_LOG_ANALYSIS,
    SYSTEM_METRIC_ANALYSIS,
    CorrelationResult,
    HypothesesOutput,
    LogAnalysisResult,
    MetricAnalysisResult,
)
from shieldops.agents.investigation.tools import InvestigationToolkit
from shieldops.models.base import Hypothesis
from shieldops.utils.llm import llm_structured

logger = structlog.get_logger()

# Module-level toolkit reference, set by the runner at graph construction time.
_toolkit: InvestigationToolkit | None = None


def set_toolkit(toolkit: InvestigationToolkit) -> None:
    """Configure the toolkit used by all nodes. Called once at startup."""
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> InvestigationToolkit:
    if _toolkit is None:
        return InvestigationToolkit()  # Empty toolkit — safe for tests
    return _toolkit


async def gather_context(state: InvestigationState) -> dict:
    """Gather initial context about the alert and affected resources.

    Queries Kubernetes events and resource health for the affected resource.
    """
    start = datetime.now(UTC)
    toolkit = _get_toolkit()
    resource_id = state.alert_context.resource_id or ""

    logger.info(
        "investigation_gathering_context",
        alert_id=state.alert_id,
        alert_name=state.alert_context.alert_name,
        resource_id=resource_id,
    )

    # Gather K8s events and health in parallel-safe manner
    k8s_events = await toolkit.get_k8s_events(resource_id) if resource_id else []
    health = await toolkit.get_resource_health(resource_id) if resource_id else {}

    event_summary = "; ".join(
        f"{e.get('reason', '?')}: {e.get('message', '')}" for e in k8s_events[:5]
    )

    step = ReasoningStep(
        step_number=1,
        action="gather_context",
        input_summary=f"Alert: {state.alert_context.alert_name} ({state.alert_context.severity})",
        output_summary=(
            f"Resource health: {health.get('status', 'unknown')}. "
            f"Found {len(k8s_events)} K8s events. {event_summary[:200]}"
        ),
        duration_ms=_elapsed_ms(start),
        tool_used="k8s_connector",
    )

    return {
        "investigation_start": start,
        "reasoning_chain": [step],
        "current_step": "gather_context",
    }


async def analyze_logs(state: InvestigationState) -> dict:
    """Query and analyze logs using the LLM to identify error patterns."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()
    resource_id = state.alert_context.resource_id or ""

    logger.info("investigation_analyzing_logs", alert_id=state.alert_id)

    # Query logs from all sources
    error_patterns = ["error", "fatal", "timeout", "connection refused", "OOMKilled"]
    log_data = await toolkit.query_logs(
        resource_id=resource_id,
        patterns=error_patterns,
    )

    # Build context for LLM analysis
    log_context = _format_log_context(state, log_data)

    # LLM analysis of log data
    findings: list[LogFinding] = []
    output_summary = (
        f"Queried logs: {log_data['total_entries']} entries, {log_data['error_count']} errors"
    )

    if log_data["total_entries"] > 0:
        try:
            analysis: LogAnalysisResult = await llm_structured(
                system_prompt=SYSTEM_LOG_ANALYSIS,
                user_prompt=log_context,
                schema=LogAnalysisResult,
            )
            output_summary = analysis.summary

            for _i, pattern in enumerate(analysis.error_patterns):
                match_count = sum(len(v) for v in log_data["pattern_matches"].values())
                findings.append(
                    LogFinding(
                        source=", ".join(log_data["sources_queried"]),
                        query=resource_id,
                        summary=pattern,
                        severity=analysis.severity,
                        sample_entries=[
                            e.get("message", "") for e in log_data["error_entries"][:5]
                        ],
                        count=match_count,
                    )
                )
        except Exception as e:
            logger.error("llm_log_analysis_failed", error=str(e))
            output_summary = (
                f"LLM analysis failed: {e}. Raw: {log_data['error_count']} errors found."
            )
            # Fallback: create findings from raw data
            if log_data["error_count"] > 0:
                findings.append(
                    LogFinding(
                        source=", ".join(log_data["sources_queried"]),
                        query=resource_id,
                        summary=f"{log_data['error_count']} error log entries found",
                        severity="error",
                        sample_entries=[
                            e.get("message", "") for e in log_data["error_entries"][:5]
                        ],
                        count=log_data["error_count"],
                    )
                )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_logs",
        input_summary=(
            f"Querying logs for {resource_id}: "
            f"{log_data['total_entries']} entries "
            f"from {log_data['sources_queried']}"
        ),
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="query_logs + llm",
    )

    return {
        "log_findings": findings,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_logs",
    }


async def analyze_metrics(state: InvestigationState) -> dict:
    """Analyze metrics for anomalies using the LLM to interpret results."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()
    resource_id = state.alert_context.resource_id or ""

    logger.info("investigation_analyzing_metrics", alert_id=state.alert_id)

    metric_data = await toolkit.query_metrics(resource_id=resource_id)

    anomalies: list[MetricAnomaly] = []
    output_summary = (
        f"Checked {len(metric_data['metrics_checked'])} metrics, "
        f"{metric_data['anomaly_count']} anomalies"
    )

    # Convert raw anomalies to MetricAnomaly models
    for raw in metric_data["anomalies"]:
        anomalies.append(
            MetricAnomaly(
                metric_name=raw.get("metric_name", "unknown"),
                source=", ".join(metric_data["sources_queried"]),
                current_value=raw.get("current_value", 0),
                baseline_value=raw.get("baseline_value", 0),
                deviation_percent=raw.get("deviation_percent", 0),
                started_at=datetime.now(UTC),
                labels=raw.get("labels", {}),
            )
        )

    # LLM analysis if we have data
    if metric_data["current_values"] or anomalies:
        metric_context = _format_metric_context(state, metric_data)
        try:
            analysis: MetricAnalysisResult = await llm_structured(
                system_prompt=SYSTEM_METRIC_ANALYSIS,
                user_prompt=metric_context,
                schema=MetricAnalysisResult,
            )
            output_summary = (
                f"{analysis.summary}. "
                f"Resource pressure: {analysis.resource_pressure}. "
                f"Bottleneck: {analysis.likely_bottleneck or 'none detected'}"
            )
        except Exception as e:
            logger.error("llm_metric_analysis_failed", error=str(e))

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_metrics",
        input_summary=f"Checking {len(metric_data['metrics_checked'])} metrics for {resource_id}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="query_metrics + llm",
    )

    return {
        "metric_anomalies": anomalies,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_metrics",
    }


async def analyze_traces(state: InvestigationState) -> dict:
    """Analyze distributed traces to find bottleneck services."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    # Extract service name from resource_id or alert labels
    service_name = (
        state.alert_context.labels.get("service")
        or state.alert_context.labels.get("app")
        or (state.alert_context.resource_id or "").split("/")[-1]
    )

    logger.info("investigation_analyzing_traces", alert_id=state.alert_id, service=service_name)

    trace_data = await toolkit.query_traces(service_name=service_name)

    trace_result: TraceResult | None = None
    output_summary = (
        f"Found {len(trace_data['traces'])} slow traces, "
        f"{len(trace_data['error_traces'])} error traces"
    )

    if trace_data["bottleneck"]:
        bn = trace_data["bottleneck"]
        trace_result = TraceResult(
            trace_id=bn.get("trace_id", "unknown"),
            root_service=service_name,
            bottleneck_service=bn.get("service"),
            error_service=bn.get("error_service"),
            total_duration_ms=bn.get("duration_ms", 0),
            spans=trace_data["traces"][:5],
        )
        output_summary += f". Bottleneck: {bn.get('service', 'unknown')}"

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_traces",
        input_summary=f"Tracing request paths for service: {service_name}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="query_traces",
    )

    return {
        "trace_analysis": trace_result,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_traces",
    }


async def correlate_findings(state: InvestigationState) -> dict:
    """Correlate findings across logs, metrics, and traces using the LLM."""
    start = datetime.now(UTC)

    logger.info(
        "investigation_correlating",
        alert_id=state.alert_id,
        log_findings=len(state.log_findings),
        metric_anomalies=len(state.metric_anomalies),
    )

    correlated: list[CorrelatedEvent] = []
    output_summary = "No findings to correlate"

    all_findings = _format_all_findings(state)

    if state.log_findings or state.metric_anomalies:
        try:
            result: CorrelationResult = await llm_structured(
                system_prompt=SYSTEM_CORRELATION,
                user_prompt=all_findings,
                schema=CorrelationResult,
            )

            for _i, event_desc in enumerate(result.correlated_events):
                correlated.append(
                    CorrelatedEvent(
                        timestamp=datetime.now(UTC),
                        source="cross-correlation",
                        event_type="correlated",
                        description=event_desc,
                        correlation_score=0.8,
                    )
                )

            output_summary = (
                f"Causal chain: {result.causal_chain[:200]}. "
                f"Found {len(correlated)} correlated events."
            )
        except Exception as e:
            logger.error("llm_correlation_failed", error=str(e))
            output_summary = f"Correlation failed: {e}"

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="correlate_findings",
        input_summary=(
            f"Correlating {len(state.log_findings)} log findings, "
            f"{len(state.metric_anomalies)} metric anomalies"
        ),
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="llm",
    )

    return {
        "correlated_events": correlated,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "correlate_findings",
    }


async def generate_hypotheses(state: InvestigationState) -> dict:
    """Generate ranked root cause hypotheses using the LLM."""
    start = datetime.now(UTC)

    logger.info("investigation_generating_hypotheses", alert_id=state.alert_id)

    all_context = _format_full_investigation_context(state)
    hypotheses: list[Hypothesis] = []
    confidence_score = 0.0

    try:
        result: HypothesesOutput = await llm_structured(
            system_prompt=SYSTEM_HYPOTHESIS_GENERATION,
            user_prompt=all_context,
            schema=HypothesesOutput,
        )

        for i, h in enumerate(result.hypotheses):
            hypotheses.append(
                Hypothesis(
                    id=f"hyp-{state.alert_id}-{i + 1}",
                    description=h.description,
                    confidence=h.confidence,
                    evidence=h.evidence,
                    affected_resources=h.affected_resources,
                    recommended_action=h.recommended_action,
                    reasoning_chain=h.reasoning,
                )
            )

        # Top hypothesis confidence is the overall confidence score
        if hypotheses:
            confidence_score = hypotheses[0].confidence

        output_summary = (
            f"Generated {len(hypotheses)} hypotheses. "
            f"Top: {hypotheses[0].description[:100] if hypotheses else 'none'} "
            f"(confidence: {confidence_score:.2f})"
        )
    except Exception as e:
        logger.error("llm_hypothesis_generation_failed", error=str(e))
        output_summary = f"Hypothesis generation failed: {e}"

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="generate_hypotheses",
        input_summary="Synthesizing all findings into root cause hypotheses",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="llm",
    )

    return {
        "hypotheses": hypotheses,
        "confidence_score": confidence_score,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "generate_hypotheses",
    }


# --- Context formatting helpers ---


def _elapsed_ms(start: datetime) -> int:
    return int((datetime.now(UTC) - start).total_seconds() * 1000)


def _format_log_context(state: InvestigationState, log_data: dict[str, Any]) -> str:
    """Format log data into a prompt for LLM analysis."""
    lines = [
        "## Alert Context",
        f"Alert: {state.alert_context.alert_name}",
        f"Severity: {state.alert_context.severity}",
        f"Resource: {state.alert_context.resource_id}",
        f"Description: {state.alert_context.description or 'N/A'}",
        "",
        "## Log Summary",
        f"Total entries: {log_data['total_entries']}",
        f"Errors: {log_data['error_count']}",
        f"Warnings: {log_data['warning_count']}",
        f"Sources: {', '.join(log_data['sources_queried'])}",
        "",
        "## Error Log Entries (most recent)",
    ]
    for entry in log_data["error_entries"][:20]:
        lines.append(f"[{entry.get('level', '?')}] {entry.get('message', '')[:300]}")

    lines.append("")
    lines.append("## Pattern Matches")
    for pattern, matches in log_data["pattern_matches"].items():
        lines.append(f"- '{pattern}': {len(matches)} matches")
        for m in matches[:3]:
            lines.append(f"  {m.get('message', '')[:200]}")

    return "\n".join(lines)


def _format_metric_context(state: InvestigationState, metric_data: dict[str, Any]) -> str:
    """Format metric data into a prompt for LLM analysis."""
    lines = [
        "## Alert Context",
        f"Alert: {state.alert_context.alert_name}",
        f"Resource: {state.alert_context.resource_id}",
        "",
        "## Current Metric Values",
    ]
    for metric, value in metric_data["current_values"].items():
        lines.append(f"- {metric}: {value}")

    lines.append("")
    lines.append(f"## Anomalies Detected ({metric_data['anomaly_count']})")
    for a in metric_data["anomalies"][:10]:
        lines.append(
            f"- {a.get('metric_name', '?')}: current={a.get('current_value')}, "
            f"baseline={a.get('baseline_value')}, "
            f"deviation={a.get('deviation_percent')}%"
        )

    # Include prior log findings for cross-referencing
    if state.log_findings:
        lines.append("")
        lines.append("## Prior Log Findings")
        for f in state.log_findings:
            lines.append(f"- [{f.severity}] {f.summary}")

    return "\n".join(lines)


def _format_all_findings(state: InvestigationState) -> str:
    """Format all findings for cross-source correlation."""
    lines = [
        "## Alert",
        f"Name: {state.alert_context.alert_name}",
        f"Severity: {state.alert_context.severity}",
        f"Resource: {state.alert_context.resource_id}",
        f"Triggered: {state.alert_context.triggered_at}",
        "",
        f"## Log Findings ({len(state.log_findings)})",
    ]
    for f in state.log_findings:
        lines.append(f"- [{f.severity}] {f.summary} (count: {f.count})")
        for sample in f.sample_entries[:3]:
            lines.append(f"  > {sample[:200]}")

    lines.append("")
    lines.append(f"## Metric Anomalies ({len(state.metric_anomalies)})")
    for a in state.metric_anomalies:
        lines.append(
            f"- {a.metric_name}: {a.current_value} (baseline: {a.baseline_value}, "
            f"deviation: {a.deviation_percent}%)"
        )

    if state.trace_analysis:
        t = state.trace_analysis
        lines.append("")
        lines.append("## Trace Analysis")
        lines.append(f"Root service: {t.root_service}")
        lines.append(f"Bottleneck: {t.bottleneck_service or 'none'}")
        lines.append(f"Error service: {t.error_service or 'none'}")
        lines.append(f"Total duration: {t.total_duration_ms}ms")

    return "\n".join(lines)


def _format_full_investigation_context(state: InvestigationState) -> str:
    """Format the complete investigation context for hypothesis generation."""
    lines = [_format_all_findings(state)]

    lines.append("")
    lines.append("## Correlated Events")
    for e in state.correlated_events:
        lines.append(f"- [{e.source}] {e.description} (score: {e.correlation_score})")

    lines.append("")
    lines.append("## Investigation Reasoning Chain")
    for step in state.reasoning_chain:
        lines.append(f"Step {step.step_number} ({step.action}): {step.output_summary}")

    return "\n".join(lines)
