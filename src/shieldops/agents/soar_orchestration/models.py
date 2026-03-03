"""State models for the SOAROrchestrationRunner LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TriageResult(BaseModel):
    """A triage result result."""

    incident_id: str = ""
    severity: str = "medium"
    category: str = ""
    confidence: float = 0.0
    indicators: list[str] = Field(default_factory=list)


class PlaybookSelection(BaseModel):
    """A playbook selection result."""

    playbook_id: str = ""
    playbook_name: str = ""
    match_score: float = 0.0
    actions_count: int = 0


class ResponseAction(BaseModel):
    """A response action result."""

    action_id: str = ""
    action_type: str = ""
    target: str = ""
    status: str = "pending"
    duration_ms: int = 0


class SOARReasoningStep(BaseModel):
    """Audit trail entry for the soar_orchestration workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class SOAROrchestrationState(BaseModel):
    """Full state for a soar_orchestration workflow run through the LangGraph workflow."""

    session_id: str = ""
    incident_config: dict[str, Any] = Field(default_factory=dict)
    triage_result: TriageResult | None = None
    playbook_selection: PlaybookSelection | None = None
    response_actions: list[ResponseAction] = Field(default_factory=list)
    actions_executed: int = 0
    actions_succeeded: int = 0
    validation_passed: bool = False
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[SOARReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
