"""Add api_keys table for programmatic API key management.

Revision ID: 011_add_api_keys
Revises: 010_add_agent_context
Create Date: 2026-02-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "011_add_api_keys"
down_revision = "010_add_agent_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=True),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "scopes",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index(
        "ix_api_keys_organization_id",
        "api_keys",
        ["organization_id"],
    )
    op.create_index(
        "ix_api_keys_key_hash",
        "api_keys",
        ["key_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_index("ix_api_keys_organization_id", table_name="api_keys")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")
