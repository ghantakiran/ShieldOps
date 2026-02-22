"""Initial schema -- all tables from ORM models.

Creates all 20 tables: investigations, remediations, audit_log, agent_sessions,
users, agent_registrations, incident_outcomes, learning_cycles, security_scans,
vulnerabilities, teams, team_members, vulnerability_comments,
team_notification_configs, vulnerability_risk_acceptances, agent_context,
organizations, playbooks, api_keys, onboarding_progress,
notification_preferences.

Revision ID: 001
Revises: None
Create Date: 2026-02-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, JSONB

from alembic import op  # type: ignore[attr-defined]

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(256), unique=True, nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.String(32), server_default="viewer"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── investigations ────────────────────────────────────────────────
    op.create_table(
        "investigations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("alert_id", sa.String(128), index=True),
        sa.Column("alert_name", sa.String(256), server_default=""),
        sa.Column("severity", sa.String(32), server_default="warning"),
        sa.Column("status", sa.String(32), server_default="init", index=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("hypotheses", JSONB, server_default="[]"),
        sa.Column("reasoning_chain", JSONB, server_default="[]"),
        sa.Column("alert_context", JSONB, server_default="{}"),
        sa.Column("log_findings", JSONB, server_default="[]"),
        sa.Column("metric_anomalies", JSONB, server_default="[]"),
        sa.Column("recommended_action", JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── remediations ──────────────────────────────────────────────────
    op.create_table(
        "remediations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("action_type", sa.String(128), index=True),
        sa.Column("target_resource", sa.String(256)),
        sa.Column("environment", sa.String(32), index=True),
        sa.Column("risk_level", sa.String(32)),
        sa.Column("status", sa.String(32), server_default="init", index=True),
        sa.Column("validation_passed", sa.Boolean, nullable=True),
        sa.Column("reasoning_chain", JSONB, server_default="[]"),
        sa.Column("action_data", JSONB, server_default="{}"),
        sa.Column("execution_result", JSONB, nullable=True),
        sa.Column("snapshot_data", JSONB, nullable=True),
        sa.Column("investigation_id", sa.String(64), nullable=True, index=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── audit_log ─────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), index=True),
        sa.Column("agent_type", sa.String(64)),
        sa.Column("action", sa.String(128), index=True),
        sa.Column("target_resource", sa.String(256)),
        sa.Column("environment", sa.String(32), index=True),
        sa.Column("risk_level", sa.String(32)),
        sa.Column("policy_evaluation", sa.String(32)),
        sa.Column("approval_status", sa.String(32), nullable=True),
        sa.Column("outcome", sa.String(32)),
        sa.Column("reasoning", sa.Text, server_default=""),
        sa.Column("actor", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_env_ts", "audit_log", ["environment", "timestamp"])

    # ── agent_sessions ────────────────────────────────────────────────
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_type", sa.String(64), index=True),
        sa.Column("event_type", sa.String(64)),
        sa.Column("status", sa.String(32), server_default="started", index=True),
        sa.Column("input_data", JSONB, nullable=True),
        sa.Column("result_data", JSONB, nullable=True),
        sa.Column("duration_ms", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── agent_registrations ───────────────────────────────────────────
    op.create_table(
        "agent_registrations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_type", sa.String(64), index=True),
        sa.Column("environment", sa.String(32), server_default="production"),
        sa.Column("status", sa.String(32), server_default="idle", index=True),
        sa.Column("config", JSONB, server_default="{}"),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── incident_outcomes ─────────────────────────────────────────────
    op.create_table(
        "incident_outcomes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("alert_type", sa.String(128), index=True),
        sa.Column("environment", sa.String(32), index=True),
        sa.Column("root_cause", sa.Text, server_default=""),
        sa.Column("resolution_action", sa.String(128), server_default=""),
        sa.Column("investigation_id", sa.String(64), nullable=True, index=True),
        sa.Column("remediation_id", sa.String(64), nullable=True, index=True),
        sa.Column("investigation_duration_ms", sa.Integer, server_default="0"),
        sa.Column("remediation_duration_ms", sa.Integer, server_default="0"),
        sa.Column("was_automated", sa.Boolean, server_default=sa.text("false")),
        sa.Column("was_correct", sa.Boolean, server_default=sa.text("true")),
        sa.Column("feedback", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_incident_outcomes_alert_env",
        "incident_outcomes",
        ["alert_type", "environment"],
    )

    # ── learning_cycles ───────────────────────────────────────────────
    op.create_table(
        "learning_cycles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("learning_type", sa.String(32), index=True),
        sa.Column("target_period", sa.String(16), server_default="30d"),
        sa.Column("status", sa.String(32), server_default="init", index=True),
        sa.Column("total_incidents_analyzed", sa.Integer, server_default="0"),
        sa.Column("recurring_pattern_count", sa.Integer, server_default="0"),
        sa.Column("improvement_score", sa.Float, server_default="0"),
        sa.Column("automation_accuracy", sa.Float, server_default="0"),
        sa.Column("pattern_insights", JSONB, server_default="[]"),
        sa.Column("playbook_updates", JSONB, server_default="[]"),
        sa.Column("threshold_adjustments", JSONB, server_default="[]"),
        sa.Column("reasoning_chain", JSONB, server_default="[]"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── security_scans ────────────────────────────────────────────────
    op.create_table(
        "security_scans",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("scan_type", sa.String(32), index=True),
        sa.Column("environment", sa.String(32), index=True),
        sa.Column("status", sa.String(32), server_default="init", index=True),
        sa.Column("cve_findings", JSONB, server_default="[]"),
        sa.Column("critical_cve_count", sa.Integer, server_default="0"),
        sa.Column("credential_statuses", JSONB, server_default="[]"),
        sa.Column("compliance_controls", JSONB, server_default="[]"),
        sa.Column("compliance_score", sa.Float, server_default="0"),
        sa.Column("patch_results", JSONB, server_default="[]"),
        sa.Column("rotation_results", JSONB, server_default="[]"),
        sa.Column("patches_applied", sa.Integer, server_default="0"),
        sa.Column("credentials_rotated", sa.Integer, server_default="0"),
        sa.Column("posture_data", JSONB, nullable=True),
        sa.Column("reasoning_chain", JSONB, server_default="[]"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_security_scans_env_created",
        "security_scans",
        ["environment", "created_at"],
    )

    # ── vulnerabilities ───────────────────────────────────────────────
    op.create_table(
        "vulnerabilities",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("cve_id", sa.String(64), index=True, nullable=True),
        sa.Column("scan_id", sa.String(64), index=True, nullable=True),
        sa.Column("source", sa.String(32)),
        sa.Column("scanner_type", sa.String(32), index=True),
        sa.Column("severity", sa.String(16), index=True),
        sa.Column("cvss_score", sa.Float, server_default="0"),
        sa.Column("title", sa.Text, server_default=""),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("package_name", sa.String(256), server_default=""),
        sa.Column("affected_resource", sa.String(512)),
        sa.Column("status", sa.String(32), server_default="new", index=True),
        sa.Column("assigned_team_id", sa.String(64), nullable=True),
        sa.Column("assigned_user_id", sa.String(64), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_breached", sa.Boolean, server_default=sa.text("false"), index=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("remediated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remediation_steps", JSONB, server_default="[]"),
        sa.Column("scan_metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_vulns_cve_resource", "vulnerabilities", ["cve_id", "affected_resource"])
    op.create_index("ix_vulns_status_severity", "vulnerabilities", ["status", "severity"])
    op.create_index("ix_vulns_team", "vulnerabilities", ["assigned_team_id"])
    op.create_index("ix_vulns_sla", "vulnerabilities", ["sla_breached", "sla_due_at"])

    # ── teams ─────────────────────────────────────────────────────────
    op.create_table(
        "teams",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256), unique=True),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("slack_channel", sa.String(128), server_default=""),
        sa.Column("pagerduty_service_id", sa.String(128), server_default=""),
        sa.Column("email", sa.String(256), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── team_members ──────────────────────────────────────────────────
    op.create_table(
        "team_members",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("team_id", sa.String(64), index=True),
        sa.Column("user_id", sa.String(64), index=True),
        sa.Column("role", sa.String(32), server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── vulnerability_comments ────────────────────────────────────────
    op.create_table(
        "vulnerability_comments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("vulnerability_id", sa.String(64), index=True),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("comment_type", sa.String(32), server_default="comment"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── team_notification_configs ─────────────────────────────────────
    op.create_table(
        "team_notification_configs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("channel_type", sa.String(32), index=True),
        sa.Column("channel_name", sa.String(256)),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column("config", JSONB, server_default="{}"),
        sa.Column("metric_name", sa.String(128), nullable=True),
        sa.Column("threshold", sa.Float, nullable=True),
        sa.Column("duration", sa.String(16), nullable=True),
        sa.Column("severity", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── vulnerability_risk_acceptances ────────────────────────────────
    op.create_table(
        "vulnerability_risk_acceptances",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("vulnerability_id", sa.String(64), index=True),
        sa.Column("accepted_by", sa.String(64)),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── agent_context ─────────────────────────────────────────────────
    op.create_table(
        "agent_context",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_type", sa.String(64), index=True),
        sa.Column("context_key", sa.String(256), index=True),
        sa.Column("context_value", JSONB, server_default="{}"),
        sa.Column("ttl_hours", sa.Integer, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_agent_context_type_key",
        "agent_context",
        ["agent_type", "context_key"],
        unique=True,
    )

    # ── organizations ─────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256), unique=True, nullable=False),
        sa.Column("slug", sa.String(128), unique=True, nullable=False),
        sa.Column("plan", sa.String(32), server_default="free"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("settings", JSONB, server_default="{}"),
        sa.Column("rate_limit", sa.Integer, server_default="1000"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # ── playbooks ─────────────────────────────────────────────────────
    op.create_table(
        "playbooks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tags", JSON, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_playbooks_name", "playbooks", ["name"])
    op.create_index("ix_playbooks_is_active", "playbooks", ["is_active"])

    # ── api_keys ──────────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("organization_id", sa.String(64), nullable=True, index=True),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("scopes", JSON, nullable=False, server_default="[]"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── onboarding_progress ───────────────────────────────────────────
    op.create_table(
        "onboarding_progress",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), index=True),
        sa.Column("step_name", sa.String(64), index=True),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "step_name", name="uq_onboarding_org_step"),
    )
    op.create_index("ix_onboarding_org_id", "onboarding_progress", ["org_id"])

    # ── notification_preferences ──────────────────────────────────────
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("config", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "channel", "event_type", name="uq_user_channel_event"),
    )
    op.create_index(
        "ix_notification_preferences_user_id",
        "notification_preferences",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_preferences_user_id",
        table_name="notification_preferences",
    )
    op.drop_table("notification_preferences")
    op.drop_index("ix_onboarding_org_id", table_name="onboarding_progress")
    op.drop_table("onboarding_progress")
    op.drop_table("api_keys")
    op.drop_index("ix_playbooks_is_active", table_name="playbooks")
    op.drop_index("ix_playbooks_name", table_name="playbooks")
    op.drop_table("playbooks")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
    op.drop_index("ix_agent_context_type_key", table_name="agent_context")
    op.drop_table("agent_context")
    op.drop_table("vulnerability_risk_acceptances")
    op.drop_table("team_notification_configs")
    op.drop_table("vulnerability_comments")
    op.drop_table("team_members")
    op.drop_table("teams")
    op.drop_index("ix_vulns_sla", table_name="vulnerabilities")
    op.drop_index("ix_vulns_team", table_name="vulnerabilities")
    op.drop_index("ix_vulns_status_severity", table_name="vulnerabilities")
    op.drop_index("ix_vulns_cve_resource", table_name="vulnerabilities")
    op.drop_table("vulnerabilities")
    op.drop_index("ix_security_scans_env_created", table_name="security_scans")
    op.drop_table("security_scans")
    op.drop_table("learning_cycles")
    op.drop_index("ix_incident_outcomes_alert_env", table_name="incident_outcomes")
    op.drop_table("incident_outcomes")
    op.drop_table("agent_registrations")
    op.drop_table("agent_sessions")
    op.drop_index("ix_audit_log_env_ts", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("remediations")
    op.drop_table("investigations")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
