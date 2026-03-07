"""Pydantic v2 models for Kubernetes remediation actions."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class K8sActionType(StrEnum):
    """Supported Kubernetes remediation action types."""

    RESTART_POD = "restart_pod"
    RESTART_DEPLOYMENT = "restart_deployment"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    SCALE_DEPLOYMENT = "scale_deployment"
    SCALE_HPA = "scale_hpa"
    CORDON_NODE = "cordon_node"
    DRAIN_NODE = "drain_node"
    UPDATE_CONFIG_MAP = "update_config_map"
    UPDATE_RESOURCE_LIMITS = "update_resource_limits"
    DELETE_EVICTED_PODS = "delete_evicted_pods"


class RiskLevel(StrEnum):
    """Risk classification for remediation actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RemediationStatus(StrEnum):
    """Status of a remediation action execution."""

    PENDING = "pending"
    POLICY_CHECK = "policy_check"
    APPROVED = "approved"
    DENIED = "denied"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ApprovalRequirement(StrEnum):
    """Approval workflow level required for an action."""

    AUTO_APPROVE = "auto_approve"
    NOTIFY = "notify"
    REQUIRE_APPROVAL = "require_approval"


class K8sRemediationRequest(BaseModel):
    """Request to execute a Kubernetes remediation action."""

    action_type: K8sActionType
    namespace: str
    resource_name: str
    environment: str = "production"
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    initiated_by: str = "remediation_agent"
    investigation_id: str | None = None


class RemediationResult(BaseModel):
    """Result of an executed remediation action."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    action_type: K8sActionType
    namespace: str
    resource_name: str
    environment: str
    status: RemediationStatus
    risk_level: RiskLevel = RiskLevel.MEDIUM
    before_state: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    snapshot_id: str | None = None
    duration_seconds: float = 0.0
    message: str = ""
    error: str | None = None
    audit_log: list[str] = Field(default_factory=list)
    initiated_by: str = "remediation_agent"
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class PolicyDecision(BaseModel):
    """Result of OPA policy evaluation for a remediation action."""

    allowed: bool
    reason: str
    risk_level: RiskLevel
    requires_approval: ApprovalRequirement = ApprovalRequirement.AUTO_APPROVE
    violated_policies: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResourceSnapshot(BaseModel):
    """Serialized Kubernetes resource state for rollback."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    resource_type: str  # deployment, configmap, hpa, node
    resource_name: str
    namespace: str
    state_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    action_id: str | None = None
    expires_at: datetime | None = None
