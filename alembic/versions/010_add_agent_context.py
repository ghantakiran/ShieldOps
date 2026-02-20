"""Add agent_context table for persistent cross-incident memory.

Revision ID: 010_add_agent_context
Revises: 009_add_organizations
Create Date: 2026-02-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "010_add_agent_context"
down_revision = "009_add_organizations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_context",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_type", sa.String(64), nullable=False),
        sa.Column("context_key", sa.String(256), nullable=False),
        sa.Column(
            "context_value",
            JSONB,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("ttl_hours", sa.Integer, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index(
        "ix_agent_context_agent_type",
        "agent_context",
        ["agent_type"],
    )
    op.create_index(
        "ix_agent_context_context_key",
        "agent_context",
        ["context_key"],
    )
    op.create_index(
        "ix_agent_context_type_key",
        "agent_context",
        ["agent_type", "context_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_context_type_key", table_name="agent_context")
    op.drop_index("ix_agent_context_context_key", table_name="agent_context")
    op.drop_index("ix_agent_context_agent_type", table_name="agent_context")
    op.drop_table("agent_context")
