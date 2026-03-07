"""Add war_rooms and war_room_responders tables.

Supports the PagerDuty war room integration for automated incident coordination.

Revision ID: 002
Revises: 001
Create Date: 2026-03-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op  # type: ignore[attr-defined]

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── war_rooms ──────────────────────────────────────────────────────
    op.create_table(
        "war_rooms",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("incident_id", sa.String(128), index=True, nullable=False),
        sa.Column("title", sa.String(512), server_default=""),
        sa.Column("severity", sa.String(16), server_default="P2"),
        sa.Column("status", sa.String(32), server_default="active", index=True),
        sa.Column("slack_channel_id", sa.String(128), server_default=""),
        sa.Column("slack_channel_name", sa.String(256), server_default=""),
        sa.Column("pagerduty_incident_id", sa.String(128), server_default=""),
        sa.Column("escalation_level", sa.Integer, server_default="1"),
        sa.Column("resolution_summary", sa.Text, server_default=""),
        sa.Column("timeline", JSONB, server_default="[]"),
        sa.Column("extra_data", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_war_rooms_incident_status",
        "war_rooms",
        ["incident_id", "status"],
    )

    # ── war_room_responders ────────────────────────────────────────────
    op.create_table(
        "war_room_responders",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("war_room_id", sa.String(64), index=True, nullable=False),
        sa.Column("user_name", sa.String(256), nullable=False),
        sa.Column("user_email", sa.String(256), server_default=""),
        sa.Column("role", sa.String(64), server_default="responder"),
        sa.Column("status", sa.String(32), server_default="paged"),
        sa.Column("pagerduty_user_id", sa.String(128), server_default=""),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_wrr_room_user",
        "war_room_responders",
        ["war_room_id", "user_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_wrr_room_user", table_name="war_room_responders")
    op.drop_table("war_room_responders")
    op.drop_index("ix_war_rooms_incident_status", table_name="war_rooms")
    op.drop_table("war_rooms")
