"""Initial schema — investigations, remediations, audit_log, agent_sessions.

Revision ID: 001
Revises: None
Create Date: 2026-02-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("agent_sessions")
    op.drop_index("ix_audit_log_env_ts", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("remediations")
    op.drop_table("investigations")
