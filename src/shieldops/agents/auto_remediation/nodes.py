"""Node implementations for the Auto Remediation Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.auto_remediation.models import (
    AutoRemediationState,
    RemediationReasoningStep,
)
from shieldops.agents.auto_remediation.tools import AutoRemediationToolkit

logger = structlog.get_logger()

_toolkit: AutoRemediationToolkit | None = None


def set_toolkit(toolkit: AutoRemediationToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> AutoRemediationToolkit:
    if _toolkit is None:
        return AutoRemediationToolkit()
    return _toolkit


async def assess_issue(state: AutoRemediationState) -> dict[str, Any]:
    """Assess the issue to be remediated."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("assess_issue", 1.0)

    step = RemediationReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="assess_issue",
        input_summary="Executing assess_issue",
        output_summary="Completed assess_issue",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="assess_issue",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "assess_issue",
        "session_start": start,
    }


async def plan_remediation(state: AutoRemediationState) -> dict[str, Any]:
    """Plan the remediation strategy."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("plan_remediation", 1.0)

    step = RemediationReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="plan_remediation",
        input_summary="Executing plan_remediation",
        output_summary="Completed plan_remediation",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="plan_remediation",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "plan_remediation",
    }


async def execute_fix(state: AutoRemediationState) -> dict[str, Any]:
    """Execute the remediation fix."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("execute_fix", 1.0)

    step = RemediationReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="execute_fix",
        input_summary="Executing execute_fix",
        output_summary="Completed execute_fix",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="execute_fix",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "execute_fix",
    }


async def verify_resolution(state: AutoRemediationState) -> dict[str, Any]:
    """Verify the issue is resolved."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("verify_resolution", 1.0)

    step = RemediationReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="verify_resolution",
        input_summary="Executing verify_resolution",
        output_summary="Completed verify_resolution",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="verify_resolution",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "verify_resolution",
    }


async def finalize_remediation(state: AutoRemediationState) -> dict[str, Any]:
    """Finalize the remediation session."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_metric("auto_remediation_duration_ms", float(duration_ms))

    step = RemediationReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_remediation",
        input_summary="Finalizing auto_remediation session",
        output_summary=f"Session complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
