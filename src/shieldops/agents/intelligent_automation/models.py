"""State models for the IntelligentAutomationRunner LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IntelligentAutomationReasoningStep(BaseModel):
    """Audit trail entry for the intelligent_automation workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class IntelligentAutomationState(BaseModel):
    """Full state for a intelligent_automation workflow run through the LangGraph workflow."""

    session_id: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    assessment_score: float = 0.0
    strategy_count: int = 0
    actions_executed: int = 0
    actions_succeeded: int = 0
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[IntelligentAutomationReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
