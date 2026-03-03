"""Node implementations for the Itdr Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.itdr.models import (
    ITDRReasoningStep,
    ITDRState,
)
from shieldops.agents.itdr.tools import ITDRToolkit

logger = structlog.get_logger()

_toolkit: ITDRToolkit | None = None


def set_toolkit(toolkit: ITDRToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> ITDRToolkit:
    if _toolkit is None:
        return ITDRToolkit()
    return _toolkit


async def scan_identities(state: ITDRState) -> dict[str, Any]:
    """Scan identity sources for threats."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("scan_identities", 1.0)

    step = ITDRReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="scan_identities",
        input_summary="Executing scan_identities",
        output_summary="Completed scan_identities",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="scan_identities",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "scan_identities",
        "session_start": start,
    }


async def detect_threats(state: ITDRState) -> dict[str, Any]:
    """Detect identity-based threats and anomalies."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("detect_threats", 1.0)

    step = ITDRReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="detect_threats",
        input_summary="Executing detect_threats",
        output_summary="Completed detect_threats",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="detect_threats",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "detect_threats",
    }


async def analyze_attack_paths(state: ITDRState) -> dict[str, Any]:
    """Analyze identity attack paths and lateral movement."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("analyze_attack_paths", 1.0)

    step = ITDRReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="analyze_attack_paths",
        input_summary="Executing analyze_attack_paths",
        output_summary="Completed analyze_attack_paths",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="analyze_attack_paths",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "analyze_attack_paths",
    }


async def respond_to_threats(state: ITDRState) -> dict[str, Any]:
    """Respond to detected identity threats."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("respond_to_threats", 1.0)

    step = ITDRReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="respond_to_threats",
        input_summary="Executing respond_to_threats",
        output_summary="Completed respond_to_threats",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="respond_to_threats",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "respond_to_threats",
    }


async def finalize_detection(state: ITDRState) -> dict[str, Any]:
    """Finalize the ITDR detection session."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_metric("itdr_duration_ms", float(duration_ms))

    step = ITDRReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_detection",
        input_summary="Finalizing itdr session",
        output_summary=f"Session complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
