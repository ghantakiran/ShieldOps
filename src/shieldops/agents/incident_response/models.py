"""State models for the Incident Response Agent LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ContainmentAction(BaseModel):
    """A containment action to isolate threats."""

    action_id: str = ""
    action_type: str = ""
    target: str = ""
    status: str = "pending"
    risk_level: str = "medium"
    automated: bool = False
    result: dict[str, Any] = Field(default_factory=dict)


class EradicationStep(BaseModel):
    """An eradication step to remove threats."""

    step_id: str = ""
    step_type: str = ""
    target: str = ""
    status: str = "pending"
    description: str = ""


class RecoveryTask(BaseModel):
    """A recovery task to restore services."""

    task_id: str = ""
    task_type: str = ""
    service: str = ""
    status: str = "pending"
    priority: str = "medium"
    estimated_duration_min: int = 0


class ResponseReasoningStep(BaseModel):
    """Audit trail entry for the incident response workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class IncidentResponseState(BaseModel):
    """Full state for an incident response workflow run through the LangGraph workflow."""

    # Input
    incident_id: str = ""
    incident_data: dict[str, Any] = Field(default_factory=dict)

    # Assessment
    severity: str = "medium"
    assessment_score: float = 0.0
    incident_type: str = ""

    # Containment
    containment_actions: list[ContainmentAction] = Field(default_factory=list)
    containment_complete: bool = False

    # Eradication
    eradication_steps: list[EradicationStep] = Field(default_factory=list)
    eradication_complete: bool = False

    # Recovery
    recovery_tasks: list[RecoveryTask] = Field(default_factory=list)
    recovery_complete: bool = False

    # Validation
    validation_passed: bool = False
    validation_results: dict[str, Any] = Field(default_factory=dict)

    # Workflow tracking
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[ResponseReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
