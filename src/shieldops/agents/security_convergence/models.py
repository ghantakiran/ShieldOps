"""State models for the SecurityConvergenceRunner LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SecurityConvergenceReasoningStep(BaseModel):
    """Audit trail entry for the security_convergence workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class SecurityConvergenceState(BaseModel):
    """Full state for a security_convergence workflow run through the LangGraph workflow."""

    session_id: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    posture_count: int = 0
    signal_count: int = 0
    defense_count: int = 0
    response_count: int = 0
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[SecurityConvergenceReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
