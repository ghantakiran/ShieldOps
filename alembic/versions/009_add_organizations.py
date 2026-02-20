"""Add organizations table and organization_id to tenant-scoped tables.

Revision ID: 009_add_organizations
Revises: 008_newsletter_escalation
Create Date: 2026-02-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "009_add_organizations"
down_revision = "008_newsletter_escalation"
branch_labels = None
depends_on = None

# Tables that gain an organization_id foreign key
_TENANT_TABLES = [
    "users",
    "investigations",
    "remediations",
    "vulnerabilities",
    "audit_log",
]


def upgrade() -> None:
    # 1. Create the organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(256), unique=True, nullable=False),
        sa.Column("slug", sa.String(128), unique=True, nullable=False),
        sa.Column(
            "plan",
            sa.String(32),
            server_default="free",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("settings", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "rate_limit",
            sa.Integer,
            server_default=sa.text("1000"),
            nullable=False,
        ),
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
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    # 2. Add organization_id column to each tenant-scoped table
    for table in _TENANT_TABLES:
        op.add_column(
            table,
            sa.Column(
                "organization_id",
                sa.String(64),
                nullable=True,
            ),
        )
        op.create_index(
            f"ix_{table}_organization_id",
            table,
            ["organization_id"],
        )


def downgrade() -> None:
    # Drop organization_id columns (reverse order)
    for table in reversed(_TENANT_TABLES):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_column(table, "organization_id")

    # Drop organizations table
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
