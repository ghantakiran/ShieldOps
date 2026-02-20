"""Add playbooks table for custom playbook storage.

Revision ID: 012_add_playbooks_table
Revises: 011_add_api_keys
Create Date: 2026-02-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "012_add_playbooks_table"
down_revision = "011_add_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "playbooks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, default=""),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "tags",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_playbooks_name", "playbooks", ["name"])
    op.create_index(
        "ix_playbooks_is_active",
        "playbooks",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_playbooks_is_active", table_name="playbooks")
    op.drop_index("ix_playbooks_name", table_name="playbooks")
    op.drop_table("playbooks")
