"""State models for the Zero Trust Agent LangGraph workflow."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IdentityVerification(BaseModel):
    """An identity verification result from zero trust assessment."""

    identity_id: str = ""
    identity_type: str = ""
    risk_level: str = "low"
    verified: bool = False
    trust_score: float = 0.0


class DeviceAssessment(BaseModel):
    """A device posture assessment result."""

    device_id: str = ""
    device_type: str = ""
    posture_status: str = "unknown"
    compliance_score: float = 0.0
    issues: list[str] = Field(default_factory=list)


class AccessEvaluation(BaseModel):
    """An access request evaluation result."""

    access_id: str = ""
    resource: str = ""
    action: str = ""
    decision: str = "deny"
    risk_factors: list[str] = Field(default_factory=list)


class ZeroTrustReasoningStep(BaseModel):
    """Audit trail entry for the zero trust workflow."""

    step_number: int
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int = 0
    tool_used: str | None = None


class ZeroTrustState(BaseModel):
    """Full state for a zero trust assessment run through the LangGraph workflow."""

    # Input
    session_id: str = ""
    assessment_config: dict[str, Any] = Field(default_factory=dict)

    # Identity verification
    identity_verifications: list[IdentityVerification] = Field(default_factory=list)
    identity_verified: int = 0

    # Device assessment
    device_assessments: list[DeviceAssessment] = Field(default_factory=list)

    # Access evaluation
    access_evaluations: list[AccessEvaluation] = Field(default_factory=list)
    violation_count: int = 0

    # Policy enforcement
    trust_score: float = 0.0
    enforcement_actions: list[dict[str, Any]] = Field(default_factory=list)
    policy_enforced: bool = False

    # Workflow tracking
    session_start: datetime | None = None
    session_duration_ms: int = 0
    reasoning_chain: list[ZeroTrustReasoningStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
