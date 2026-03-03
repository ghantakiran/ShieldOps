"""Node implementations for the ObservabilityIntelligence Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.observability_intelligence.models import (
    ObservabilityIntelligenceReasoningStep,
    ObservabilityIntelligenceState,
)
from shieldops.agents.observability_intelligence.tools import ObservabilityIntelligenceToolkit

logger = structlog.get_logger()

_toolkit: ObservabilityIntelligenceToolkit | None = None


def set_toolkit(toolkit: ObservabilityIntelligenceToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> ObservabilityIntelligenceToolkit:
    if _toolkit is None:
        return ObservabilityIntelligenceToolkit()
    return _toolkit


async def collect_signals(state: ObservabilityIntelligenceState) -> dict[str, Any]:
    """Collect observability signals from multiple sources"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("collect_signals", 1.0)

    step = ObservabilityIntelligenceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="collect_signals",
        input_summary="Executing collect_signals",
        output_summary="Completed collect_signals",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="collect_signals",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "collect_signals",
        "session_start": start,
    }


async def correlate_data(state: ObservabilityIntelligenceState) -> dict[str, Any]:
    """Correlate data across metrics, logs, and traces"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("correlate_data", 1.0)

    step = ObservabilityIntelligenceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="correlate_data",
        input_summary="Executing correlate_data",
        output_summary="Completed correlate_data",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="correlate_data",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "correlate_data",
    }


async def analyze_insights(state: ObservabilityIntelligenceState) -> dict[str, Any]:
    """Analyze correlated data for actionable insights"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("analyze_insights", 1.0)

    step = ObservabilityIntelligenceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_insights",
        input_summary="Executing analyze_insights",
        output_summary="Completed analyze_insights",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="analyze_insights",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_insights",
    }


async def generate_recommendations(state: ObservabilityIntelligenceState) -> dict[str, Any]:
    """Generate optimization recommendations"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("generate_recommendations", 1.0)

    step = ObservabilityIntelligenceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="generate_recommendations",
        input_summary="Executing generate_recommendations",
        output_summary="Completed generate_recommendations",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="generate_recommendations",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "generate_recommendations",
    }


async def finalize_analysis(state: ObservabilityIntelligenceState) -> dict[str, Any]:
    """Finalize the observability analysis session"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_metric("observability_intelligence_duration_ms", float(duration_ms))

    step = ObservabilityIntelligenceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_analysis",
        input_summary="Finalizing observability_intelligence session",
        output_summary=f"Session complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
