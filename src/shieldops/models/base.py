"""Base data models shared across all ShieldOps components."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Environment(StrEnum):
    """Target environment for agent operations."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class RiskLevel(StrEnum):
    """Risk classification for agent actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentStatus(StrEnum):
    """Current status of an agent instance."""

    IDLE = "idle"
    INVESTIGATING = "investigating"
    REMEDIATING = "remediating"
    WAITING_APPROVAL = "waiting_approval"
    ERROR = "error"
    DISABLED = "disabled"


class ExecutionStatus(StrEnum):
    """Status of an action execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class ApprovalStatus(StrEnum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"
    ESCALATED = "escalated"


class TimeRange(BaseModel):
    """Time range for queries."""

    start: datetime
    end: datetime


class Resource(BaseModel):
    """Unified representation of an infrastructure resource."""

    id: str
    name: str
    resource_type: str  # pod, node, instance, service, etc.
    environment: Environment
    provider: str  # aws, gcp, azure, kubernetes, linux
    namespace: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class HealthStatus(BaseModel):
    """Health status of a resource."""

    resource_id: str
    healthy: bool
    status: str  # running, stopped, crash_looping, degraded, etc.
    message: str | None = None
    last_checked: datetime
    metrics: dict[str, float] = Field(default_factory=dict)


class AlertContext(BaseModel):
    """Context from a triggered alert."""

    alert_id: str
    alert_name: str
    severity: str  # critical, warning, info
    source: str  # prometheus, datadog, cloudwatch, etc.
    resource_id: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    triggered_at: datetime
    description: str | None = None
    runbook_url: str | None = None


class Hypothesis(BaseModel):
    """Root cause hypothesis from investigation."""

    id: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str]
    affected_resources: list[str]
    recommended_action: str | None = None
    reasoning_chain: list[str]


class RemediationAction(BaseModel):
    """A remediation action to execute."""

    id: str
    action_type: str  # restart_pod, scale_horizontal, rollback_deployment, etc.
    target_resource: str
    environment: Environment
    risk_level: RiskLevel
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str
    estimated_duration_seconds: int = 60
    rollback_capable: bool = True


class ActionResult(BaseModel):
    """Result of an executed action."""

    action_id: str
    status: ExecutionStatus
    message: str
    started_at: datetime
    completed_at: datetime | None = None
    snapshot_id: str | None = None
    validation_passed: bool | None = None
    error: str | None = None


class Snapshot(BaseModel):
    """Infrastructure state snapshot for rollback."""

    id: str
    resource_id: str
    snapshot_type: str  # k8s_resource, aws_state, linux_config
    state: dict[str, Any]
    created_at: datetime
    expires_at: datetime | None = None


class AuditEntry(BaseModel):
    """Immutable audit trail entry."""

    id: str
    timestamp: datetime
    agent_type: str
    action: str
    target_resource: str
    environment: Environment
    risk_level: RiskLevel
    policy_evaluation: str  # allowed, denied, override
    approval_status: ApprovalStatus | None = None
    outcome: ExecutionStatus
    reasoning: str
    actor: str  # agent_id or user_id
