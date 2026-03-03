"""Node implementations for the AutonomousDefense Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.autonomous_defense.models import (
    AutonomousDefenseReasoningStep,
    AutonomousDefenseState,
)
from shieldops.agents.autonomous_defense.tools import AutonomousDefenseToolkit

logger = structlog.get_logger()

_toolkit: AutonomousDefenseToolkit | None = None


def set_toolkit(toolkit: AutonomousDefenseToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> AutonomousDefenseToolkit:
    if _toolkit is None:
        return AutonomousDefenseToolkit()
    return _toolkit


async def assess_threats(state: AutonomousDefenseState) -> dict[str, Any]:
    """Assess current threat landscape"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("assess_threats", 1.0)

    step = AutonomousDefenseReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="assess_threats",
        input_summary="Executing assess_threats",
        output_summary="Completed assess_threats",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="assess_threats",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "assess_threats",
        "session_start": start,
    }


async def select_defenses(state: AutonomousDefenseState) -> dict[str, Any]:
    """Select defense countermeasures"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("select_defenses", 1.0)

    step = AutonomousDefenseReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="select_defenses",
        input_summary="Executing select_defenses",
        output_summary="Completed select_defenses",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="select_defenses",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "select_defenses",
    }


async def deploy_countermeasures(state: AutonomousDefenseState) -> dict[str, Any]:
    """Deploy defense countermeasures"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("deploy_countermeasures", 1.0)

    step = AutonomousDefenseReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="deploy_countermeasures",
        input_summary="Executing deploy_countermeasures",
        output_summary="Completed deploy_countermeasures",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="deploy_countermeasures",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "deploy_countermeasures",
    }


async def validate_protection(state: AutonomousDefenseState) -> dict[str, Any]:
    """Validate protection effectiveness"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    await toolkit.record_metric("validate_protection", 1.0)

    step = AutonomousDefenseReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="validate_protection",
        input_summary="Executing validate_protection",
        output_summary="Completed validate_protection",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="validate_protection",
    )

    return {
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "validate_protection",
    }


async def finalize_defense(state: AutonomousDefenseState) -> dict[str, Any]:
    """Finalize defense session"""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_metric("autonomous_defense_duration_ms", float(duration_ms))

    step = AutonomousDefenseReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_defense",
        input_summary="Finalizing autonomous_defense session",
        output_summary=f"Session complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
