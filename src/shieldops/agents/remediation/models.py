"""State models for the Remediation Agent."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shieldops.models.base import (
    ActionResult,
    AlertContext,
    ApprovalStatus,
    AuditEntry,
    ExecutionStatus,
    RemediationAction,
    RiskLevel,
    Snapshot,
)


class PolicyResult(BaseModel):
    """Result of OPA policy evaluation."""

    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    evaluated_at: datetime | None = None


class ValidationCheck(BaseModel):
    """Result of a post-action health validation."""

    check_name: str
    passed: bool
    message: str
    checked_at: datetime | None = None


class RemediationStep(BaseModel):
    """A single step in the remediation agent's reasoning chain."""

    step_number: int
    action: str  # evaluate_policy, assess_risk, create_snapshot, execute, validate, etc.
    input_summary: str
    output_summary: str
    duration_ms: int
    tool_used: str | None = None


class RemediationState(BaseModel):
    """Full state of a remediation workflow (LangGraph state)."""

    # Input
    remediation_id: str = ""
    action: RemediationAction
    alert_context: AlertContext | None = None
    investigation_id: str | None = None

    # Policy & risk
    policy_result: PolicyResult | None = None
    assessed_risk: RiskLevel | None = None

    # Approval
    approval_status: ApprovalStatus | None = None
    approval_request_id: str | None = None

    # Execution
    snapshot: Snapshot | None = None
    execution_result: ActionResult | None = None

    # Validation
    validation_checks: list[ValidationCheck] = Field(default_factory=list)
    validation_passed: bool | None = None

    # Rollback
    rollback_result: ActionResult | None = None

    # Metadata
    remediation_start: datetime | None = None
    remediation_duration_ms: int = 0
    reasoning_chain: list[RemediationStep] = Field(default_factory=list)
    current_step: str = "init"
    error: str | None = None
