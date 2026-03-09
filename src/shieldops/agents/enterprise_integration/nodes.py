"""Node implementations for the Enterprise Integration Agent LangGraph workflow.

Each node is an async function that:
1. Queries external systems via the IntegrationToolkit
2. Uses the LLM to analyze and reason about the data
3. Updates the integration state with findings
4. Records its reasoning step in the audit trail
"""

from datetime import UTC, datetime
from typing import Any, cast

import structlog

from shieldops.agents.enterprise_integration.models import (
    DiagnosticFinding,
    IntegrationConfig,
    IntegrationState,
    IntegrationStatus,
    ReasoningStep,
)
from shieldops.agents.enterprise_integration.prompts import (
    SYSTEM_DIAGNOSE_INTEGRATION,
    SYSTEM_RECOMMEND_FIXES,
    DiagnosisResult,
    FixRecommendationsOutput,
)
from shieldops.agents.enterprise_integration.tools import IntegrationToolkit
from shieldops.utils.llm import llm_structured

logger = structlog.get_logger()

# Module-level toolkit reference, set by the runner at graph construction time.
_toolkit: IntegrationToolkit | None = None


def set_toolkit(toolkit: IntegrationToolkit) -> None:
    """Configure the toolkit used by all nodes. Called once at startup."""
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> IntegrationToolkit:
    if _toolkit is None:
        return IntegrationToolkit()  # Empty toolkit — safe for tests
    return _toolkit


async def load_config(state: IntegrationState) -> dict[str, Any]:
    """Load integration configuration from the repository."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "integration_loading_config",
        integration_id=state.integration_id,
        action=state.action,
    )

    config: IntegrationConfig | None = None
    output_summary = "No configuration found"

    if toolkit._repository is not None:
        try:
            raw = await toolkit._repository.get_integration_config(
                state.integration_id,
            )
            if raw:
                config = IntegrationConfig.model_validate(raw)
                output_summary = (
                    f"Loaded config: provider={config.provider}, "
                    f"category={config.category}, auth={config.auth_type}, "
                    f"enabled={config.enabled}"
                )
        except Exception as e:
            logger.error(
                "config_load_failed",
                integration_id=state.integration_id,
                error=str(e),
            )
            output_summary = f"Config load failed: {e}"

    step = ReasoningStep(
        step_number=1,
        action="load_config",
        input_summary=f"Integration: {state.integration_id}, action: {state.action}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="repository",
    )

    return {
        "config": config,
        "action_start": start,
        "reasoning_chain": [step],
        "current_step": "load_config",
    }


async def check_health(state: IntegrationState) -> dict[str, Any]:
    """Run health checks: endpoint reachability, auth validity, latency."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "integration_checking_health",
        integration_id=state.integration_id,
    )

    # Perform health check
    health = await toolkit.check_health(state.integration_id)

    # Test authentication if we have a config
    auth_result: dict[str, Any] = {}
    if state.config is not None:
        auth_result = await toolkit.test_authentication(state.config)
        if not auth_result.get("valid", False):
            health.status = IntegrationStatus.DEGRADED
            health.error_message = health.error_message or auth_result.get(
                "message", "Auth invalid"
            )

    # Measure latency if we have an endpoint
    latency_result: dict[str, Any] = {}
    if state.config is not None:
        latency_result = await toolkit.measure_latency(state.config.endpoint_url)
        if latency_result.get("latency_ms", -1) >= 0:
            health.latency_ms = latency_result["latency_ms"]
        if not latency_result.get("reachable", False):
            health.status = IntegrationStatus.ERROR
            health.error_message = "Endpoint unreachable"

    # Check rate limit
    rate_limit = await toolkit.get_rate_limit_status(state.integration_id)

    status_changed = False
    if state.health is not None and state.health.status != health.status:
        status_changed = True

    output_summary = (
        f"Status: {health.status}, latency: {health.latency_ms:.0f}ms, "
        f"auth_valid: {auth_result.get('valid', 'unknown')}, "
        f"errors_1h: {health.error_count_1h}, "
        f"rate_limit_remaining: {rate_limit.get('requests_remaining', 'N/A')}"
    )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="check_health",
        input_summary=f"Health check for {state.integration_id}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="health_check + auth_test + latency",
    )

    return {
        "health": health,
        "status_changed": status_changed,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "check_health",
    }


async def analyze_sync_history(state: IntegrationState) -> dict[str, Any]:
    """Analyze recent sync patterns for anomalies."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "integration_analyzing_sync",
        integration_id=state.integration_id,
    )

    sync_events = await toolkit.get_sync_history(state.integration_id, hours=24)

    # Compute sync statistics
    total = len(sync_events)
    failed = [e for e in sync_events if e.status == "failed"]
    avg_duration = sum(e.duration_ms for e in sync_events) / total if total > 0 else 0
    failure_rate = len(failed) / total if total > 0 else 0.0

    diagnostics: list[DiagnosticFinding] = []
    if failure_rate > 0.3:
        diagnostics.append(
            DiagnosticFinding(
                severity="error",
                component="sync_pipeline",
                finding=(
                    f"High sync failure rate: {failure_rate:.0%} "
                    f"({len(failed)}/{total} events failed in 24h)"
                ),
                recommendation="Investigate error logs and consider reconnecting the integration",
            )
        )
    if avg_duration > 5000 and total > 0:
        diagnostics.append(
            DiagnosticFinding(
                severity="warning",
                component="sync_performance",
                finding=f"Elevated average sync duration: {avg_duration:.0f}ms",
                recommendation=(
                    "Check endpoint latency and payload sizes; "
                    "consider batching or increasing timeouts"
                ),
            )
        )

    output_summary = (
        f"Analyzed {total} sync events (24h). "
        f"Failures: {len(failed)} ({failure_rate:.0%}). "
        f"Avg duration: {avg_duration:.0f}ms. "
        f"Diagnostics raised: {len(diagnostics)}"
    )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_sync_history",
        input_summary=f"Sync history for {state.integration_id} (24h)",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="get_sync_history",
    )

    return {
        "sync_events": sync_events,
        "diagnostics": [*state.diagnostics, *diagnostics],
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_sync_history",
    }


async def diagnose_issues(state: IntegrationState) -> dict[str, Any]:
    """Use the LLM to diagnose problems when health is degraded or error."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "integration_diagnosing",
        integration_id=state.integration_id,
        status=state.health.status if state.health else "unknown",
    )

    # Gather error logs for context
    error_logs = await toolkit.get_error_logs(state.integration_id, hours=6)

    # Build LLM context
    context = _format_diagnosis_context(state, error_logs)
    diagnostics: list[DiagnosticFinding] = list(state.diagnostics)
    output_summary = "No diagnosis performed"

    try:
        result = cast(
            DiagnosisResult,
            await llm_structured(
                system_prompt=SYSTEM_DIAGNOSE_INTEGRATION,
                user_prompt=context,
                schema=DiagnosisResult,
            ),
        )

        diagnostics.append(
            DiagnosticFinding(
                severity=result.severity,
                component=", ".join(result.affected_components),
                finding=result.root_cause,
                recommendation="; ".join(result.fix_steps),
            )
        )

        output_summary = (
            f"Root cause: {result.root_cause[:150]}. "
            f"Severity: {result.severity}. "
            f"Affected: {', '.join(result.affected_components)}. "
            f"Recovery: {result.estimated_recovery}"
        )
    except Exception as e:
        logger.error("llm_diagnosis_failed", error=str(e))
        output_summary = f"LLM diagnosis failed: {e}"

        # Fallback: create a diagnostic from raw error logs
        if error_logs:
            recent_msg = error_logs[0].get("message", "Unknown error")
            diagnostics.append(
                DiagnosticFinding(
                    severity="error",
                    component="unknown",
                    finding=f"LLM unavailable. Latest error: {recent_msg[:200]}",
                    recommendation="Manual investigation required",
                )
            )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="diagnose_issues",
        input_summary=(
            f"Diagnosing {state.integration_id} "
            f"(status={state.health.status if state.health else 'unknown'}, "
            f"error_logs={len(error_logs)})"
        ),
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="get_error_logs + llm",
    )

    return {
        "diagnostics": diagnostics,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "diagnose_issues",
    }


async def apply_fixes(state: IntegrationState) -> dict[str, Any]:
    """Apply automated fixes: retry connection, rotate credentials, etc."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "integration_applying_fixes",
        integration_id=state.integration_id,
        diagnostics_count=len(state.diagnostics),
    )

    actions_taken: list[str] = []
    fix_result: dict[str, Any] = {"fixes_applied": [], "fixes_failed": []}

    for diag in state.diagnostics:
        recommendation_lower = diag.recommendation.lower()

        # Auto-rotate credentials when diagnosis suggests it
        if "rotat" in recommendation_lower and "credential" in recommendation_lower:
            cred_result = await toolkit.rotate_credentials(state.integration_id)
            if cred_result.get("rotated"):
                actions_taken.append("Rotated credentials")
                fix_result["fixes_applied"].append("rotate_credentials")
            else:
                fix_result["fixes_failed"].append(
                    f"rotate_credentials: {cred_result.get('message', 'unknown')}"
                )

        # Auto-reconnect when diagnosis suggests it
        if "reconnect" in recommendation_lower:
            health = await toolkit.check_health(state.integration_id)
            if health.status == IntegrationStatus.CONNECTED:
                actions_taken.append("Reconnected successfully")
                fix_result["fixes_applied"].append("reconnect")
            else:
                fix_result["fixes_failed"].append(f"reconnect: status={health.status}")

    output_summary = (
        f"Applied {len(fix_result['fixes_applied'])} fixes, "
        f"{len(fix_result['fixes_failed'])} failed. "
        f"Actions: {'; '.join(actions_taken) or 'none'}"
    )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="apply_fixes",
        input_summary=f"Applying fixes for {len(state.diagnostics)} diagnostics",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="rotate_credentials + check_health",
    )

    return {
        "result": fix_result,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "apply_fixes",
    }


async def generate_recommendations(state: IntegrationState) -> dict[str, Any]:
    """Generate improvement recommendations using the LLM."""
    start = datetime.now(UTC)

    logger.info(
        "integration_generating_recommendations",
        integration_id=state.integration_id,
    )

    context = _format_recommendation_context(state)
    recommendations: list[str] = []
    output_summary = "No recommendations generated"

    try:
        result = cast(
            FixRecommendationsOutput,
            await llm_structured(
                system_prompt=SYSTEM_RECOMMEND_FIXES,
                user_prompt=context,
                schema=FixRecommendationsOutput,
            ),
        )

        for rec in result.recommendations:
            recommendations.append(
                f"[{rec.priority}] {rec.action}: {rec.description} "
                f"(automated={rec.automated}, risk={rec.risk_level})"
            )

        output_summary = (
            f"Generated {len(recommendations)} recommendations. "
            f"Top: {recommendations[0][:120] if recommendations else 'none'}"
        )
    except Exception as e:
        logger.error("llm_recommendation_failed", error=str(e))
        output_summary = f"Recommendation generation failed: {e}"

        # Fallback: derive basic recommendations from diagnostics
        for diag in state.diagnostics:
            recommendations.append(f"[{diag.severity}] {diag.component}: {diag.recommendation}")

    # Calculate total processing duration
    processing_duration_ms = 0
    if state.action_start:
        processing_duration_ms = int(
            (datetime.now(UTC) - state.action_start).total_seconds() * 1000
        )

    step = ReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="generate_recommendations",
        input_summary="Synthesizing recommendations from diagnostics and health data",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="llm",
    )

    return {
        "recommendations": recommendations,
        "processing_duration_ms": processing_duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }


# --- Context formatting helpers ---


def _elapsed_ms(start: datetime) -> int:
    return int((datetime.now(UTC) - start).total_seconds() * 1000)


def _format_diagnosis_context(
    state: IntegrationState,
    error_logs: list[dict[str, Any]],
) -> str:
    """Format integration data into a prompt for LLM diagnosis."""
    lines = ["## Integration Configuration"]
    if state.config:
        lines.extend(
            [
                f"Provider: {state.config.provider}",
                f"Category: {state.config.category}",
                f"Direction: {state.config.direction}",
                f"Auth type: {state.config.auth_type}",
                f"Endpoint: {state.config.endpoint_url}",
                f"Enabled: {state.config.enabled}",
            ]
        )
    else:
        lines.append("Configuration not available")

    lines.append("")
    lines.append("## Health Status")
    if state.health:
        lines.extend(
            [
                f"Status: {state.health.status}",
                f"Latency: {state.health.latency_ms:.0f}ms",
                f"Errors (1h): {state.health.error_count_1h}",
                f"Uptime (24h): {state.health.uptime_percent_24h:.1f}%",
                f"Last successful sync: {state.health.last_successful_sync or 'never'}",
                f"Error message: {state.health.error_message or 'none'}",
            ]
        )
    else:
        lines.append("Health data not available")

    lines.append("")
    lines.append(f"## Sync Events ({len(state.sync_events)} recent)")
    for event in state.sync_events[:20]:
        lines.append(
            f"- [{event.status}] {event.event_type} ({event.direction}) "
            f"duration={event.duration_ms}ms"
            f"{f' error={event.error}' if event.error else ''}"
        )

    lines.append("")
    lines.append(f"## Error Logs ({len(error_logs)} entries)")
    for log in error_logs[:30]:
        lines.append(
            f"[{log.get('timestamp', '?')}] [{log.get('level', '?')}] "
            f"{log.get('message', '')[:300]}"
        )

    lines.append("")
    lines.append(f"## Existing Diagnostics ({len(state.diagnostics)})")
    for diag in state.diagnostics:
        lines.append(f"- [{diag.severity}] {diag.component}: {diag.finding}")

    return "\n".join(lines)


def _format_recommendation_context(state: IntegrationState) -> str:
    """Format the complete state for recommendation generation."""
    lines = ["## Integration Summary"]
    if state.config:
        lines.extend(
            [
                f"Provider: {state.config.provider}",
                f"Category: {state.config.category}",
                f"Direction: {state.config.direction}",
                f"Auth type: {state.config.auth_type}",
            ]
        )

    lines.append("")
    lines.append("## Current Health")
    if state.health:
        lines.extend(
            [
                f"Status: {state.health.status}",
                f"Latency: {state.health.latency_ms:.0f}ms",
                f"Errors (1h): {state.health.error_count_1h}",
                f"Events today: {state.health.events_today}",
                f"Uptime (24h): {state.health.uptime_percent_24h:.1f}%",
            ]
        )

    lines.append("")
    lines.append(f"## Diagnostics ({len(state.diagnostics)})")
    for diag in state.diagnostics:
        lines.append(
            f"- [{diag.severity}] {diag.component}: {diag.finding} → {diag.recommendation}"
        )

    lines.append("")
    lines.append(f"## Sync Summary ({len(state.sync_events)} events)")
    if state.sync_events:
        total = len(state.sync_events)
        failed = sum(1 for e in state.sync_events if e.status == "failed")
        avg_dur = sum(e.duration_ms for e in state.sync_events) / total
        lines.append(f"Total: {total}, Failed: {failed}, Avg duration: {avg_dur:.0f}ms")

    if state.result:
        lines.append("")
        lines.append("## Applied Fixes")
        for fix in state.result.get("fixes_applied", []):
            lines.append(f"- ✓ {fix}")
        for fail in state.result.get("fixes_failed", []):
            lines.append(f"- ✗ {fail}")

    lines.append("")
    lines.append("## Reasoning Chain")
    for step in state.reasoning_chain:
        lines.append(f"Step {step.step_number} ({step.action}): {step.output_summary}")

    return "\n".join(lines)
