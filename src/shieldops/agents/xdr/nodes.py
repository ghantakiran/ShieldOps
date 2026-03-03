"""Node implementations for the XDR Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.xdr.models import (
    XDRReasoningStep,
    XDRState,
)
from shieldops.agents.xdr.tools import XDRToolkit

logger = structlog.get_logger()

_toolkit: XDRToolkit | None = None


def set_toolkit(toolkit: XDRToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> XDRToolkit:
    if _toolkit is None:
        return XDRToolkit()
    return _toolkit


async def ingest_telemetry(state: XDRState) -> dict[str, Any]:
    """Ingest and normalize security telemetry"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("ingest_telemetry", 1.0)

    step = XDRReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="ingest_telemetry",
        input_summary="Executing ingest_telemetry",
        output_summary="Completed ingest_telemetry",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="ingest_telemetry",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "ingest_telemetry",
        "session_start": start,
    }


async def correlate_threats(state: XDRState) -> dict[str, Any]:
    """Correlate threats across detection domains"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("correlate_threats", 1.0)

    step = XDRReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="correlate_threats",
        input_summary="Executing correlate_threats",
        output_summary="Completed correlate_threats",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="correlate_threats",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "correlate_threats",
    }


async def build_attack_story(state: XDRState) -> dict[str, Any]:
    """Build comprehensive attack narrative"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("build_attack_story", 1.0)

    step = XDRReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="build_attack_story",
        input_summary="Executing build_attack_story",
        output_summary="Completed build_attack_story",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="build_attack_story",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "build_attack_story",
    }


async def execute_response(state: XDRState) -> dict[str, Any]:
    """Execute coordinated response actions"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("execute_response", 1.0)

    step = XDRReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="execute_response",
        input_summary="Executing execute_response",
        output_summary="Completed execute_response",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="execute_response",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "execute_response",
    }


async def finalize_investigation(state: XDRState) -> dict[str, Any]:
    """Finalize the XDR investigation session"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_metric("xdr_duration_ms", float(duration_ms))

    step = XDRReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_investigation",
        input_summary="Finalizing xdr session",
        output_summary=f"Session complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
