"""Supervisor agent that orchestrates specialist agents.

The supervisor receives events (alerts, schedules, manual triggers) and
delegates to the appropriate specialist agent (Investigation, Remediation,
Security, Learning). It manages the lifecycle of delegated tasks and
handles escalation when specialist agents fail or are uncertain.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class TaskType(StrEnum):
    """Types of tasks the supervisor can delegate."""

    INVESTIGATE = "investigate"
    REMEDIATE = "remediate"
    SECURITY_SCAN = "security_scan"
    LEARN = "learn"


class SupervisorTask(BaseModel):
    """A task delegated by the supervisor to a specialist agent."""

    id: str
    task_type: TaskType
    agent_id: str | None = None
    input_data: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # pending, in_progress, completed, failed, escalated
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class Supervisor:
    """Orchestrates specialist agents and manages task lifecycle.

    Workflow:
        1. Receive event (alert, schedule, manual trigger)
        2. Classify event → determine task type
        3. Delegate to specialist agent
        4. Monitor progress, handle timeout/failure
        5. Chain tasks (investigation → remediation) when appropriate
        6. Escalate to human when agents are uncertain or fail
    """

    def __init__(self) -> None:
        self._active_tasks: dict[str, SupervisorTask] = {}

    async def handle_event(self, event: dict[str, Any]) -> SupervisorTask:
        """Process an incoming event and delegate to appropriate agent."""
        task_type = self._classify_event(event)

        task = SupervisorTask(
            id=f"task-{datetime.now(UTC).timestamp()}",
            task_type=task_type,
            input_data=event,
        )
        self._active_tasks[task.id] = task

        logger.info(
            "supervisor_delegating",
            task_id=task.id,
            task_type=task_type.value,
        )

        # TODO: Dispatch to appropriate agent via message queue
        # investigation_agent.invoke(task) / remediation_agent.invoke(task) / etc.

        return task

    def _classify_event(self, event: dict[str, Any]) -> TaskType:
        """Classify an event to determine which specialist agent should handle it."""
        event_type = event.get("type", "")

        if event_type in ("alert", "incident"):
            return TaskType.INVESTIGATE
        elif event_type in ("remediation_request", "auto_heal"):
            return TaskType.REMEDIATE
        elif event_type in ("cve_alert", "compliance_drift", "credential_expiry"):
            return TaskType.SECURITY_SCAN
        elif event_type in ("incident_resolved", "feedback"):
            return TaskType.LEARN

        # Default to investigation for unknown events
        return TaskType.INVESTIGATE

    async def chain_investigation_to_remediation(
        self, investigation_task_id: str
    ) -> SupervisorTask | None:
        """After investigation completes with high confidence, auto-create remediation task."""
        investigation = self._active_tasks.get(investigation_task_id)
        if not investigation or not investigation.result:
            return None

        confidence = investigation.result.get("confidence_score", 0)
        recommended_action = investigation.result.get("recommended_action")

        if confidence >= 0.85 and recommended_action:
            remediation_task = SupervisorTask(
                id=f"task-{datetime.now(UTC).timestamp()}",
                task_type=TaskType.REMEDIATE,
                input_data={
                    "investigation_id": investigation_task_id,
                    "action": recommended_action,
                },
            )
            self._active_tasks[remediation_task.id] = remediation_task

            logger.info(
                "supervisor_chaining_remediation",
                investigation_id=investigation_task_id,
                remediation_id=remediation_task.id,
                confidence=confidence,
            )
            return remediation_task

        return None
