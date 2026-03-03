"""Node implementations for the Threat Automation Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.threat_automation.models import (
    BehaviorAnalysis,
    DetectedThreat,
    IntelCorrelation,
    ThreatAutomationState,
    ThreatReasoningStep,
)
from shieldops.agents.threat_automation.tools import ThreatAutomationToolkit

logger = structlog.get_logger()

_toolkit: ThreatAutomationToolkit | None = None


def set_toolkit(toolkit: ThreatAutomationToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> ThreatAutomationToolkit:
    if _toolkit is None:
        return ThreatAutomationToolkit()
    return _toolkit


async def detect_threats(state: ThreatAutomationState) -> dict[str, Any]:
    """Detect threats from hunt configuration and telemetry sources."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    raw_threats = await toolkit.detect_threats(state.hunt_config)
    threats = [DetectedThreat(**t) for t in raw_threats if isinstance(t, dict)]

    # Add default threat if none detected but scope is specified
    scope = state.hunt_config.get("scope", "")
    if not threats and scope:
        threats.append(
            DetectedThreat(
                threat_id="t-001",
                threat_type="reconnaissance",
                severity="medium",
                source=scope,
                confidence=50.0,
                indicators=["suspicious_scan_activity"],
            )
        )

    critical = sum(1 for t in threats if t.severity in ("critical", "high"))

    step = ThreatReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="detect_threats",
        input_summary=f"Hunting scope={scope}",
        output_summary=f"Detected {len(threats)} threats, {critical} critical/high",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="threat_detector",
    )

    await toolkit.record_hunt_metric("detection", float(len(threats)))

    return {
        "detected_threats": threats,
        "threat_count": len(threats),
        "critical_count": critical,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "detect_threats",
        "session_start": start,
    }


async def analyze_behavior(state: ThreatAutomationState) -> dict[str, Any]:
    """Analyze behavioral patterns associated with detected threats."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    threat_dicts = [t.model_dump() for t in state.detected_threats]
    raw_analyses = await toolkit.analyze_behaviors(threat_dicts)
    analyses = [BehaviorAnalysis(**a) for a in raw_analyses if isinstance(a, dict)]

    step = ThreatReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_behavior",
        input_summary=f"Analyzing behavior for {len(state.detected_threats)} threats",
        output_summary=f"Completed {len(analyses)} behavior analyses",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="behavior_analyzer",
    )

    return {
        "behavior_analyses": analyses,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_behavior",
    }


async def correlate_intelligence(state: ThreatAutomationState) -> dict[str, Any]:
    """Correlate detected threats with threat intelligence feeds."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    threat_dicts = [t.model_dump() for t in state.detected_threats]
    raw_correlations = await toolkit.correlate_intel(threat_dicts)
    correlations = [IntelCorrelation(**c) for c in raw_correlations if isinstance(c, dict)]

    # Update critical count based on intel correlation
    high_confidence = sum(1 for c in correlations if c.confidence >= 80.0)
    critical_count = state.critical_count + high_confidence

    step = ThreatReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="correlate_intelligence",
        input_summary=f"Correlating {len(state.detected_threats)} threats with intel feeds",
        output_summary=f"Found {len(correlations)} correlations, {high_confidence} high-confidence",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="intel_correlator",
    )

    return {
        "intel_correlations": correlations,
        "critical_count": critical_count,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "correlate_intelligence",
    }


async def automate_response(state: ThreatAutomationState) -> dict[str, Any]:
    """Automate response actions for critical threats."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    threat_dicts = [t.model_dump() for t in state.detected_threats]
    actions = await toolkit.execute_responses(threat_dicts)
    automated = len(actions)

    step = ThreatReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="automate_response",
        input_summary=f"Automating responses for {state.critical_count} critical threats",
        output_summary=f"Executed {automated} automated response actions",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="response_engine",
    )

    return {
        "response_actions": actions,
        "automated_responses": automated,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "automate_response",
    }


async def finalize_hunt(state: ThreatAutomationState) -> dict[str, Any]:
    """Finalize threat hunt and record metrics."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_hunt_metric("hunt_duration_ms", float(duration_ms))

    step = ThreatReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_hunt",
        input_summary=f"Finalizing hunt {state.hunt_id}",
        output_summary=f"Hunt complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
