"""Add security_scans table for security agent persistence.

Revision ID: 005
Revises: 004
Create Date: 2026-02-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "security_scans",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("scan_type", sa.String(32), index=True),
        sa.Column("environment", sa.String(32), index=True),
        sa.Column("status", sa.String(32), server_default="init", index=True),
        sa.Column("cve_findings", sa.dialects.postgresql.JSONB, server_default="[]"),
        sa.Column("critical_cve_count", sa.Integer, server_default="0"),
        sa.Column("credential_statuses", sa.dialects.postgresql.JSONB, server_default="[]"),
        sa.Column("compliance_controls", sa.dialects.postgresql.JSONB, server_default="[]"),
        sa.Column("compliance_score", sa.Float, server_default="0.0"),
        sa.Column("patch_results", sa.dialects.postgresql.JSONB, server_default="[]"),
        sa.Column("rotation_results", sa.dialects.postgresql.JSONB, server_default="[]"),
        sa.Column("patches_applied", sa.Integer, server_default="0"),
        sa.Column("credentials_rotated", sa.Integer, server_default="0"),
        sa.Column("posture_data", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("reasoning_chain", sa.dialects.postgresql.JSONB, server_default="[]"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_security_scans_env_created",
        "security_scans",
        ["environment", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_security_scans_env_created", table_name="security_scans")
    op.drop_table("security_scans")
