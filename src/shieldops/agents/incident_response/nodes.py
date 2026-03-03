"""Node implementations for the Incident Response Agent LangGraph workflow."""

from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.agents.incident_response.models import (
    ContainmentAction,
    EradicationStep,
    IncidentResponseState,
    RecoveryTask,
    ResponseReasoningStep,
)
from shieldops.agents.incident_response.tools import IncidentResponseToolkit

logger = structlog.get_logger()

_toolkit: IncidentResponseToolkit | None = None


def set_toolkit(toolkit: IncidentResponseToolkit) -> None:
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> IncidentResponseToolkit:
    if _toolkit is None:
        return IncidentResponseToolkit()
    return _toolkit


async def assess_incident(state: IncidentResponseState) -> dict[str, Any]:
    """Perform initial incident assessment and severity classification."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    incident_data = state.incident_data
    severity_input = incident_data.get("severity", "medium")

    severity_scores = {"critical": 95, "high": 80, "medium": 50, "low": 25}
    assessment_score = float(severity_scores.get(severity_input, 50))

    incident_type = incident_data.get("type", "unknown")

    step = ResponseReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="assess_incident",
        input_summary=f"Incident {state.incident_id} severity={severity_input}",
        output_summary=f"Assessment score={assessment_score}, type={incident_type}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="assessment_engine",
    )

    await toolkit.record_response_metric("assessment", assessment_score)

    return {
        "severity": severity_input,
        "assessment_score": assessment_score,
        "incident_type": incident_type,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "assess_incident",
        "session_start": start,
    }


async def plan_containment(state: IncidentResponseState) -> dict[str, Any]:
    """Plan containment actions based on incident assessment."""
    start = datetime.now(UTC)

    actions: list[ContainmentAction] = []
    if state.assessment_score >= 70:
        actions.append(
            ContainmentAction(
                action_id="c-001",
                action_type="network_isolation",
                target=state.incident_data.get("affected_host", "unknown"),
                risk_level="medium",
                automated=state.severity != "critical",
            )
        )
    if state.incident_data.get("malware_detected"):
        actions.append(
            ContainmentAction(
                action_id="c-002",
                action_type="process_kill",
                target=state.incident_data.get("malware_process", "unknown"),
                risk_level="low",
                automated=True,
            )
        )

    step = ResponseReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="plan_containment",
        input_summary=f"Severity={state.severity}, score={state.assessment_score}",
        output_summary=f"Planned {len(actions)} containment actions",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="containment_planner",
    )

    return {
        "containment_actions": actions,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "plan_containment",
    }


async def execute_containment(state: IncidentResponseState) -> dict[str, Any]:
    """Execute containment actions."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    updated_actions: list[ContainmentAction] = []
    for action in state.containment_actions:
        if action.automated:
            result = await toolkit.execute_containment(action.action_type, action.target)
            action.status = result.get("status", "failed")
            action.result = result
        updated_actions.append(action)

    all_complete = all(a.status == "completed" for a in updated_actions if a.automated)

    step = ResponseReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="execute_containment",
        input_summary=f"Executing {len(updated_actions)} containment actions",
        output_summary=f"Containment complete={all_complete}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="containment_executor",
    )

    return {
        "containment_actions": updated_actions,
        "containment_complete": all_complete,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "execute_containment",
    }


async def plan_eradication(state: IncidentResponseState) -> dict[str, Any]:
    """Plan eradication steps to remove the threat."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    raw_steps = await toolkit.plan_eradication(state.incident_type)
    steps = [EradicationStep(**s) for s in raw_steps if isinstance(s, dict)]

    if not steps and state.incident_type:
        steps.append(
            EradicationStep(
                step_id="e-001",
                step_type="malware_removal",
                target=state.incident_data.get("affected_host", "unknown"),
                description=f"Remove {state.incident_type} artifacts",
            )
        )

    step = ResponseReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="plan_eradication",
        input_summary=f"Planning eradication for {state.incident_type}",
        output_summary=f"Planned {len(steps)} eradication steps",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="eradication_planner",
    )

    return {
        "eradication_steps": steps,
        "eradication_complete": True,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "plan_eradication",
    }


async def plan_recovery(state: IncidentResponseState) -> dict[str, Any]:
    """Plan recovery tasks to restore services."""
    start = datetime.now(UTC)

    tasks: list[RecoveryTask] = []
    affected_services = state.incident_data.get("affected_services", [])
    for svc in affected_services:
        tasks.append(
            RecoveryTask(
                task_id=f"r-{len(tasks) + 1:03d}",
                task_type="service_restart",
                service=svc,
                priority="high" if state.severity in ("critical", "high") else "medium",
                estimated_duration_min=15,
            )
        )

    if not tasks:
        tasks.append(
            RecoveryTask(
                task_id="r-001",
                task_type="health_check",
                service="all",
                priority="medium",
                estimated_duration_min=5,
            )
        )

    step = ResponseReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="plan_recovery",
        input_summary=f"Planning recovery for {len(affected_services)} services",
        output_summary=f"Planned {len(tasks)} recovery tasks",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="recovery_planner",
    )

    return {
        "recovery_tasks": tasks,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "plan_recovery",
    }


async def validate_response(state: IncidentResponseState) -> dict[str, Any]:
    """Validate that incident response is complete."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    validation = await toolkit.validate_recovery(state.incident_id)
    passed = validation.get("passed", False)

    step = ResponseReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="validate_response",
        input_summary=f"Validating response for incident {state.incident_id}",
        output_summary=f"Validation passed={passed}",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used="validation_engine",
    )

    return {
        "validation_passed": passed,
        "validation_results": validation,
        "recovery_complete": True,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "validate_response",
    }


async def finalize_response(state: IncidentResponseState) -> dict[str, Any]:
    """Finalize incident response and record metrics."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    duration_ms = 0
    if state.session_start:
        duration_ms = int((datetime.now(UTC) - state.session_start).total_seconds() * 1000)

    await toolkit.record_response_metric("response_duration_ms", float(duration_ms))

    step = ResponseReasoningStep(
        step_number=len(state.reasoning_chain) + 1,
        action="finalize_response",
        input_summary=f"Finalizing response for incident {state.incident_id}",
        output_summary=f"Response complete in {duration_ms}ms",
        duration_ms=int((datetime.now(UTC) - start).total_seconds() * 1000),
        tool_used=None,
    )

    return {
        "session_duration_ms": duration_ms,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "complete",
    }
