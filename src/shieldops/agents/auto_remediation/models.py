"""State models for the AutoRemediationRunner LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IssueAssessment(BaseModel):
    """A issue assessment result."""

    issue_id: str = ""
    issue_type: str = ""
    severity: str = "medium"
    affected_services: list[str] = Field(default_factory=list)
    root_cause: str = ""


class RemediationPlan(BaseModel):
    """A remediation plan result."""

    plan_id: str = ""
    strategy: str = ""
    steps: list[str] = Field(default_factory=list)
    risk_score: float = 0.0
    estimated_duration_ms: int = 0


class FixResult(BaseModel):
    """A fix result result."""

    fix_id: str = ""
    action_type: str = ""
    target: str = ""
    status: str = "pending"
    duration_ms: int = 0


class RemediationReasoningStep(BaseModel):
    """Audit trail entry for the auto_remediation workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class AutoRemediationState(BaseModel):
    """Full state for a auto_remediation workflow run through the LangGraph workflow."""

    session_id: str = ""
    remediation_config: dict[str, Any] = Field(default_factory=dict)
    issue_assessment: IssueAssessment | None = None
    remediation_plan: RemediationPlan | None = None
    fix_results: list[FixResult] = Field(default_factory=list)
    fixes_attempted: int = 0
    fixes_succeeded: int = 0
    verification_passed: bool = False
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[RemediationReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
