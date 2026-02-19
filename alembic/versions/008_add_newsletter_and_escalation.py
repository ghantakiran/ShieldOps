"""Add newsletter and escalation tables.

Revision ID: 008_newsletter_escalation
Revises: 007_vuln_mgmt
Create Date: 2026-02-19
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "008_newsletter_escalation"
down_revision = "007_vuln_mgmt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Newsletter configuration per team
    op.create_table(
        "newsletter_config",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("team_id", sa.String(64), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="weekly"),
        sa.Column("include_new_vulns", sa.Boolean, server_default=sa.text("true")),
        sa.Column("include_sla_breaches", sa.Boolean, server_default=sa.text("true")),
        sa.Column("include_remediation_progress", sa.Boolean, server_default=sa.text("true")),
        sa.Column("include_posture_trend", sa.Boolean, server_default=sa.text("true")),
        sa.Column("include_top_risks", sa.Boolean, server_default=sa.text("true")),
        sa.Column("include_industry_alerts", sa.Boolean, server_default=sa.text("true")),
        sa.Column("max_vulnerabilities", sa.Integer, server_default=sa.text("50")),
        sa.Column("recipients", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_newsletter_config_team", "newsletter_config", ["team_id"])

    # Newsletter send history
    op.create_table(
        "newsletter_history",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "config_id",
            sa.String(64),
            sa.ForeignKey("newsletter_config.id"),
            nullable=True,
        ),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("team_id", sa.String(64), nullable=True),
        sa.Column("recipient_count", sa.Integer, server_default=sa.text("0")),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sections", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(20), server_default="sent"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_newsletter_history_sent", "newsletter_history", ["sent_at"])

    # Escalation rules per team
    op.create_table(
        "escalation_rules",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("team_id", sa.String(64), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("condition", sa.String(100), nullable=False),
        sa.Column("delay_hours", sa.Float, server_default=sa.text("0")),
        sa.Column("notify_role", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(20), server_default="high"),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_escalation_rules_team", "escalation_rules", ["team_id"])

    # Team notification channel configuration
    op.create_table(
        "team_notification_config",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("team_id", sa.String(64), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("channel_type", sa.String(50), nullable=False),
        sa.Column("channel_config", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("severity_filter", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_team_notif_config_team", "team_notification_config", ["team_id"])


def downgrade() -> None:
    op.drop_table("team_notification_config")
    op.drop_table("escalation_rules")
    op.drop_table("newsletter_history")
    op.drop_table("newsletter_config")
