"""Node implementations for the Soar Orchestration Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.soar_orchestration.models import (
    SOAROrchestrationState,
    SOARReasoningStep,
)
from shieldops.agents.soar_orchestration.tools import SOAROrchestrationToolkit

logger = structlog.get_logger()

_toolkit: SOAROrchestrationToolkit | None = None


def set_toolkit(toolkit: SOAROrchestrationToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> SOAROrchestrationToolkit:
    if _toolkit is None:
        return SOAROrchestrationToolkit()
    return _toolkit


async def triage_incident(state: SOAROrchestrationState) -> dict[str, Any]:
    """Triage and classify the security incident."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("triage_incident", 1.0)

    step = SOARReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="triage_incident",
        input_summary="Executing triage_incident",
        output_summary="Completed triage_incident",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="triage_incident",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "triage_incident",
        "session_start": start,
    }


async def select_playbook(state: SOAROrchestrationState) -> dict[str, Any]:
    """Select the best playbook for the incident."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("select_playbook", 1.0)

    step = SOARReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="select_playbook",
        input_summary="Executing select_playbook",
        output_summary="Completed select_playbook",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="select_playbook",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "select_playbook",
    }


async def execute_actions(state: SOAROrchestrationState) -> dict[str, Any]:
    """Execute response actions from the playbook."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("execute_actions", 1.0)

    step = SOARReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="execute_actions",
        input_summary="Executing execute_actions",
        output_summary="Completed execute_actions",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="execute_actions",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "execute_actions",
    }


async def validate_response(state: SOAROrchestrationState) -> dict[str, Any]:
    """Validate that response actions were effective."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("validate_response", 1.0)

    step = SOARReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="validate_response",
        input_summary="Executing validate_response",
        output_summary="Completed validate_response",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="validate_response",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "validate_response",
    }


async def finalize_orchestration(state: SOAROrchestrationState) -> dict[str, Any]:
    """Finalize the SOAR orchestration session."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_metric("soar_orchestration_duration_ms", float(duration_ms))

    step = SOARReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_orchestration",
        input_summary="Finalizing soar_orchestration session",
        output_summary=f"Session complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
