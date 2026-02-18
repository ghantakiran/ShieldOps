"""Add incident_outcomes table for learning agent analysis.

Revision ID: 004
Revises: 003
Create Date: 2026-02-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incident_outcomes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("alert_type", sa.String(128), index=True),
        sa.Column("environment", sa.String(32), index=True),
        sa.Column("root_cause", sa.Text, server_default=""),
        sa.Column("resolution_action", sa.String(128), server_default=""),
        sa.Column("investigation_id", sa.String(64), nullable=True, index=True),
        sa.Column("remediation_id", sa.String(64), nullable=True, index=True),
        sa.Column("investigation_duration_ms", sa.Integer, server_default="0"),
        sa.Column("remediation_duration_ms", sa.Integer, server_default="0"),
        sa.Column("was_automated", sa.Boolean, server_default="false"),
        sa.Column("was_correct", sa.Boolean, server_default="true"),
        sa.Column("feedback", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_incident_outcomes_alert_env",
        "incident_outcomes",
        ["alert_type", "environment"],
    )


def downgrade() -> None:
    op.drop_index("ix_incident_outcomes_alert_env", table_name="incident_outcomes")
    op.drop_table("incident_outcomes")
