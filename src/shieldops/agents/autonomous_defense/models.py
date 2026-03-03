"""State models for the AutonomousDefenseRunner LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AutonomousDefenseReasoningStep(BaseModel):
    """Audit trail entry for the autonomous_defense workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class AutonomousDefenseState(BaseModel):
    """Full state for a autonomous_defense workflow run through the LangGraph workflow."""

    session_id: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    threat_count: int = 0
    defense_count: int = 0
    countermeasure_count: int = 0
    validation_count: int = 0
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[AutonomousDefenseReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
