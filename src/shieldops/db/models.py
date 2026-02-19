"""SQLAlchemy 2.x ORM models for ShieldOps persistence."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class UserRecord(Base):
    """Platform user for authentication."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"usr-{uuid4().hex[:12]}"
    )
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InvestigationRecord(Base):
    """Persisted investigation result."""

    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(128), index=True)
    alert_name: Mapped[str] = mapped_column(String(256), default="")
    severity: Mapped[str] = mapped_column(String(32), default="warning")
    status: Mapped[str] = mapped_column(String(32), default="init", index=True)
    confidence: Mapped[float] = mapped_column(default=0.0)
    hypotheses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    reasoning_chain: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    alert_context: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    log_findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    metric_anomalies: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    recommended_action: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RemediationRecord(Base):
    """Persisted remediation result."""

    __tablename__ = "remediations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_type: Mapped[str] = mapped_column(String(128), index=True)
    target_resource: Mapped[str] = mapped_column(String(256))
    environment: Mapped[str] = mapped_column(String(32), index=True)
    risk_level: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="init", index=True)
    validation_passed: Mapped[bool | None] = mapped_column(nullable=True)
    reasoning_chain: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    action_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    execution_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    snapshot_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    investigation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    """Immutable audit trail — append-only, never UPDATE."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"aud-{uuid4().hex[:12]}"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    agent_type: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(128), index=True)
    target_resource: Mapped[str] = mapped_column(String(256))
    environment: Mapped[str] = mapped_column(String(32), index=True)
    risk_level: Mapped[str] = mapped_column(String(32))
    policy_evaluation: Mapped[str] = mapped_column(String(32))
    approval_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32))
    reasoning: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_audit_log_env_ts", "environment", "timestamp"),)


class IncidentOutcomeRecord(Base):
    """Persisted incident outcome for learning agent analysis."""

    __tablename__ = "incident_outcomes"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"inc-{uuid4().hex[:12]}"
    )
    alert_type: Mapped[str] = mapped_column(String(128), index=True)
    environment: Mapped[str] = mapped_column(String(32), index=True)
    root_cause: Mapped[str] = mapped_column(Text, default="")
    resolution_action: Mapped[str] = mapped_column(String(128), default="")
    investigation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    remediation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    investigation_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    remediation_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    was_automated: Mapped[bool] = mapped_column(Boolean, default=False)
    was_correct: Mapped[bool] = mapped_column(Boolean, default=True)
    feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_incident_outcomes_alert_env", "alert_type", "environment"),)


class LearningCycleRecord(Base):
    """Persisted learning cycle result."""

    __tablename__ = "learning_cycles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    learning_type: Mapped[str] = mapped_column(String(32), index=True)
    target_period: Mapped[str] = mapped_column(String(16), default="30d")
    status: Mapped[str] = mapped_column(String(32), default="init", index=True)
    total_incidents_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    recurring_pattern_count: Mapped[int] = mapped_column(Integer, default=0)
    improvement_score: Mapped[float] = mapped_column(default=0.0)
    automation_accuracy: Mapped[float] = mapped_column(default=0.0)

    # JSON fields for complex data
    pattern_insights: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    playbook_updates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    threshold_adjustments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    reasoning_chain: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SecurityScanRecord(Base):
    """Persisted security scan result."""

    __tablename__ = "security_scans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scan_type: Mapped[str] = mapped_column(String(32), index=True)
    environment: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="init", index=True)

    # CVE findings
    cve_findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    critical_cve_count: Mapped[int] = mapped_column(Integer, default=0)

    # Credential status
    credential_statuses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)

    # Compliance
    compliance_controls: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    compliance_score: Mapped[float] = mapped_column(default=0.0)

    # Action execution results
    patch_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    rotation_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    patches_applied: Mapped[int] = mapped_column(Integer, default=0)
    credentials_rotated: Mapped[int] = mapped_column(Integer, default=0)

    # Posture
    posture_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Metadata
    reasoning_chain: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_security_scans_env_created", "environment", "created_at"),)


class AgentSession(Base):
    """Tracks agent execution sessions for observability."""

    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_type: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="started", index=True)
    input_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentRegistration(Base):
    """Registered agent in the fleet."""

    __tablename__ = "agent_registrations"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"agt-{uuid4().hex[:12]}"
    )
    agent_type: Mapped[str] = mapped_column(String(64), index=True)
    environment: Mapped[str] = mapped_column(String(32), default="production")
    status: Mapped[str] = mapped_column(String(32), default="idle", index=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VulnerabilityRecord(Base):
    """Individual vulnerability with lifecycle tracking."""

    __tablename__ = "vulnerabilities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cve_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    scan_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(32))
    scanner_type: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    cvss_score: Mapped[float] = mapped_column(default=0.0)
    title: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    package_name: Mapped[str] = mapped_column(String(256), default="")
    affected_resource: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    assigned_team_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    remediated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remediation_steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    scan_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_vulns_cve_resource", "cve_id", "affected_resource"),
        Index("ix_vulns_status_severity", "status", "severity"),
        Index("ix_vulns_team", "assigned_team_id"),
        Index("ix_vulns_sla", "sla_breached", "sla_due_at"),
    )


class TeamRecord(Base):
    """Team definition for vulnerability assignment."""

    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"team-{uuid4().hex[:12]}"
    )
    name: Mapped[str] = mapped_column(String(256), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    slack_channel: Mapped[str] = mapped_column(String(128), default="")
    pagerduty_service_id: Mapped[str] = mapped_column(String(128), default="")
    email: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TeamMemberRecord(Base):
    """User-to-team mapping."""

    __tablename__ = "team_members"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"tm-{uuid4().hex[:12]}"
    )
    team_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(32), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VulnerabilityCommentRecord(Base):
    """Comment thread entry on a vulnerability."""

    __tablename__ = "vulnerability_comments"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"vc-{uuid4().hex[:12]}"
    )
    vulnerability_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    comment_type: Mapped[str] = mapped_column(String(32), default="comment")
    comment_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TeamNotificationConfigRecord(Base):
    """Notification configuration per team/channel."""

    __tablename__ = "team_notification_configs"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"tnc-{uuid4().hex[:12]}"
    )
    channel_type: Mapped[str] = mapped_column(
        String(32), index=True
    )  # slack, pagerduty, email, webhook
    channel_name: Mapped[str] = mapped_column(String(256))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Optional alert threshold fields for learning agent
    metric_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    threshold: Mapped[float | None] = mapped_column(nullable=True)
    duration: Mapped[str | None] = mapped_column(String(16), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RiskAcceptanceRecord(Base):
    """Risk acceptance record for a vulnerability."""

    __tablename__ = "vulnerability_risk_acceptances"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"ra-{uuid4().hex[:12]}"
    )
    vulnerability_id: Mapped[str] = mapped_column(String(64), index=True)
    accepted_by: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
