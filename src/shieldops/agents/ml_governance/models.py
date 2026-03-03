"""State models for the ML Governance Agent LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ModelAudit(BaseModel):
    """An ML model audit record."""

    audit_id: str = ""
    model_id: str = ""
    model_name: str = ""
    audit_type: str = ""
    compliance_score: float = 0.0
    risk_level: str = "low"


class GovernanceFinding(BaseModel):
    """A governance finding from model evaluation."""

    finding_id: str = ""
    finding_type: str = ""
    severity: str = "medium"
    affected_model: str = ""
    description: str = ""
    remediation: str = ""


class GovernanceReasoningStep(BaseModel):
    """Audit trail entry for the ML governance workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class MLGovernanceState(BaseModel):
    """Full state for an ML governance workflow run through the LangGraph workflow."""

    # Input
    session_id: str = ""
    audit_config: dict[str, Any] = Field(default_factory=dict)

    # Auditing
    model_audits: list[ModelAudit] = Field(default_factory=list)
    audit_count: int = 0

    # Analysis
    governance_findings: list[GovernanceFinding] = Field(default_factory=list)
    risk_score: float = 0.0

    # Prioritization
    prioritized_findings: list[dict[str, Any]] = Field(default_factory=list)
    critical_count: int = 0

    # Actions
    action_plan: list[dict[str, Any]] = Field(default_factory=list)
    action_started: bool = False

    # Workflow tracking
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[GovernanceReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
