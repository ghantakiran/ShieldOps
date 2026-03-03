"""State models for the XDRRunner LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class XDRReasoningStep(BaseModel):
    """Audit trail entry for the xdr workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class XDRState(BaseModel):
    """Full state for a xdr workflow run through the LangGraph workflow."""

    session_id: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    telemetry_count: int = 0
    threat_count: int = 0
    story_count: int = 0
    response_count: int = 0
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[XDRReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
