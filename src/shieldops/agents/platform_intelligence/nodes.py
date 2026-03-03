"""Node implementations for the PlatformIntelligence Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.platform_intelligence.models import (
    PlatformIntelligenceReasoningStep,
    PlatformIntelligenceState,
)
from shieldops.agents.platform_intelligence.tools import PlatformIntelligenceToolkit

logger = structlog.get_logger()

_toolkit: PlatformIntelligenceToolkit | None = None


def set_toolkit(toolkit: PlatformIntelligenceToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> PlatformIntelligenceToolkit:
    if _toolkit is None:
        return PlatformIntelligenceToolkit()
    return _toolkit


async def gather_telemetry(state: PlatformIntelligenceState) -> dict[str, Any]:
    """Gather platform telemetry data"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("gather_telemetry", 1.0)

    step = PlatformIntelligenceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="gather_telemetry",
        input_summary="Executing gather_telemetry",
        output_summary="Completed gather_telemetry",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="gather_telemetry",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "gather_telemetry",
        "session_start": start,
    }


async def analyze_patterns(state: PlatformIntelligenceState) -> dict[str, Any]:
    """Analyze patterns across signals"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("analyze_patterns", 1.0)

    step = PlatformIntelligenceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_patterns",
        input_summary="Executing analyze_patterns",
        output_summary="Completed analyze_patterns",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="analyze_patterns",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_patterns",
    }


async def compute_insights(state: PlatformIntelligenceState) -> dict[str, Any]:
    """Compute actionable insights"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("compute_insights", 1.0)

    step = PlatformIntelligenceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="compute_insights",
        input_summary="Executing compute_insights",
        output_summary="Completed compute_insights",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="compute_insights",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "compute_insights",
    }


async def generate_strategy(state: PlatformIntelligenceState) -> dict[str, Any]:
    """Generate optimization strategy"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("generate_strategy", 1.0)

    step = PlatformIntelligenceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="generate_strategy",
        input_summary="Executing generate_strategy",
        output_summary="Completed generate_strategy",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="generate_strategy",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "generate_strategy",
    }


async def finalize_intelligence(state: PlatformIntelligenceState) -> dict[str, Any]:
    """Finalize intelligence session"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_metric("platform_intelligence_duration_ms", float(duration_ms))

    step = PlatformIntelligenceReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_intelligence",
        input_summary="Finalizing platform_intelligence session",
        output_summary=f"Session complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
