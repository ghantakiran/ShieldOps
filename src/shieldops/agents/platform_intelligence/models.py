"""State models for the PlatformIntelligenceRunner LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PlatformIntelligenceReasoningStep(BaseModel):
    """Audit trail entry for the platform_intelligence workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class PlatformIntelligenceState(BaseModel):
    """Full state for a platform_intelligence workflow run through the LangGraph workflow."""

    session_id: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    telemetry_count: int = 0
    pattern_count: int = 0
    insight_count: int = 0
    strategy_count: int = 0
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[PlatformIntelligenceReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
