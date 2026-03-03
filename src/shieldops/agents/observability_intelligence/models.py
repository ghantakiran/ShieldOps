"""State models for the ObservabilityIntelligenceRunner LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ObservabilityIntelligenceReasoningStep(BaseModel):
    """Audit trail entry for the observability_intelligence workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class ObservabilityIntelligenceState(BaseModel):
    """Full state for a observability_intelligence workflow run through the LangGraph workflow."""

    session_id: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    signal_count: int = 0
    correlation_count: int = 0
    insight_count: int = 0
    recommendation_count: int = 0
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[ObservabilityIntelligenceReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
