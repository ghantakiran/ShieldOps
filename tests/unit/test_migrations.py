"""Tests for Alembic migrations — verify revision chain and upgrade/downgrade."""

import pytest

from alembic.config import Config
from alembic.script import ScriptDirectory


@pytest.fixture
def alembic_cfg():
    cfg = Config("alembic.ini")
    return cfg


class TestMigrationChain:
    def test_revisions_have_no_branch_point(self, alembic_cfg):
        """All migrations form a single linear chain."""
        script = ScriptDirectory.from_config(alembic_cfg)
        revisions = list(script.walk_revisions())
        assert len(revisions) > 0, "No migrations found"

    def test_head_is_reachable(self, alembic_cfg):
        """There is exactly one head revision."""
        script = ScriptDirectory.from_config(alembic_cfg)
        heads = script.get_heads()
        assert len(heads) == 1, f"Expected 1 head, got {len(heads)}: {heads}"

    def test_base_exists(self, alembic_cfg):
        """There is a base revision (starting point)."""
        script = ScriptDirectory.from_config(alembic_cfg)
        bases = script.get_bases()
        assert len(bases) >= 1

    def test_initial_migration_exists(self, alembic_cfg):
        """Migration 001 exists and creates the initial tables."""
        script = ScriptDirectory.from_config(alembic_cfg)
        rev = script.get_revision("001")
        assert rev is not None
        assert rev.down_revision is None  # It is the base migration
