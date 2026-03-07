"""Add subscriptions table and stripe_customer_id to organizations.

Revision ID: 014
Revises: 001
Create Date: 2026-03-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op  # type: ignore[attr-defined]

revision: str = "014"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Add stripe_customer_id to organizations ───────────────────────
    op.add_column(
        "organizations",
        sa.Column("stripe_customer_id", sa.String(256), nullable=True),
    )
    op.create_index(
        "ix_organizations_stripe_customer_id",
        "organizations",
        ["stripe_customer_id"],
    )

    # ── subscriptions ─────────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False, index=True),
        sa.Column("stripe_customer_id", sa.String(256), nullable=False),
        sa.Column(
            "stripe_subscription_id",
            sa.String(256),
            nullable=False,
            unique=True,
        ),
        sa.Column("plan", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", index=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean, server_default=sa.text("false")),
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
    op.create_index(
        "ix_subscriptions_stripe_subscription_id",
        "subscriptions",
        ["stripe_subscription_id"],
        unique=True,
    )
    op.create_index(
        "ix_subscriptions_org_status",
        "subscriptions",
        ["org_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_index("ix_organizations_stripe_customer_id", table_name="organizations")
    op.drop_column("organizations", "stripe_customer_id")
