"""Add agent_registrations table for fleet management.

Revision ID: 003
Revises: 002
Create Date: 2026-02-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("agent_registrations")
