"""Add learning_cycles table for learning agent persistence.

Revision ID: 006
Revises: 005
Create Date: 2026-02-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_cycles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("learning_type", sa.String(32), index=True),
        sa.Column("target_period", sa.String(16), server_default="30d"),
        sa.Column("status", sa.String(32), server_default="init", index=True),
        sa.Column("total_incidents_analyzed", sa.Integer, server_default="0"),
        sa.Column("recurring_pattern_count", sa.Integer, server_default="0"),
        sa.Column("improvement_score", sa.Float, server_default="0.0"),
        sa.Column("automation_accuracy", sa.Float, server_default="0.0"),
        sa.Column("pattern_insights", sa.dialects.postgresql.JSONB, server_default="[]"),
        sa.Column("playbook_updates", sa.dialects.postgresql.JSONB, server_default="[]"),
        sa.Column("threshold_adjustments", sa.dialects.postgresql.JSONB, server_default="[]"),
        sa.Column("reasoning_chain", sa.dialects.postgresql.JSONB, server_default="[]"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("learning_cycles")
