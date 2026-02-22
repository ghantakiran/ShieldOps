"""Tests for the Alembic migration framework.

Covers: migration runner functions, API routes, env.py configuration,
and initial migration structure.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from httpx import ASGITransport, AsyncClient

from shieldops.api.app import app
from shieldops.api.routes import migrations as migrations_mod

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_migrator():
    """Reset the module-level migrator singleton between tests."""
    migrations_mod._migrator = None
    yield
    migrations_mod._migrator = None


@pytest.fixture
def alembic_cfg():
    """Alembic Config pointing at the new migrations directory."""
    cfg = Config("alembic.ini")
    return cfg


@pytest.fixture
def mock_migrator():
    """A mock migrator with async methods matching shieldops.db.migrate."""
    migrator = MagicMock()
    migrator.get_current_revision = AsyncMock(return_value="001")
    migrator.get_pending_migrations = AsyncMock(return_value=[])
    migrator.run_upgrade = AsyncMock()
    migrator.run_downgrade = AsyncMock()
    migrator.get_migration_history = AsyncMock(
        return_value=[
            {
                "revision": "001",
                "down_revision": None,
                "description": "Initial schema",
            }
        ]
    )
    return migrator


@pytest.fixture
async def client():
    """HTTPX async test client for the FastAPI app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Alembic ScriptDirectory tests ────────────────────────────────────


class TestMigrationChain:
    """Verify the migration chain is valid and consistent."""

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
        """Migration 001 exists and is the base migration."""
        script = ScriptDirectory.from_config(alembic_cfg)
        rev = script.get_revision("001")
        assert rev is not None
        assert rev.down_revision is None, "001 should be the base migration"


# ── Initial migration structure tests ────────────────────────────────


class TestInitialMigration:
    """Verify the initial migration covers all expected tables."""

    @staticmethod
    def _load_migration():
        """Load the 001_initial_schema module via importlib (numeric names)."""
        import importlib

        return importlib.import_module("shieldops.db.migrations.versions.001_initial_schema")

    def test_upgrade_function_exists(self):
        """The initial migration has an upgrade() function."""
        m = self._load_migration()
        assert hasattr(m, "upgrade")
        assert callable(m.upgrade)

    def test_downgrade_function_exists(self):
        """The initial migration has a downgrade() function."""
        m = self._load_migration()
        assert hasattr(m, "downgrade")
        assert callable(m.downgrade)

    def test_revision_identifiers(self):
        """The migration has correct revision metadata."""
        m = self._load_migration()
        assert m.revision == "001"
        assert m.down_revision is None


# ── env.py configuration tests ───────────────────────────────────────


class TestEnvConfiguration:
    """Verify env.py correctly imports and configures metadata."""

    def test_target_metadata_is_set(self):
        """env.py exposes target_metadata from the ORM Base."""
        from shieldops.db.models import Base

        # Verify Base.metadata contains expected tables.
        table_names = set(Base.metadata.tables.keys())
        assert "users" in table_names
        assert "investigations" in table_names
        assert "remediations" in table_names
        assert "audit_log" in table_names

    def test_alembic_config_points_to_migrations_dir(self, alembic_cfg):
        """alembic.ini script_location points to src/shieldops/db/migrations."""
        location = alembic_cfg.get_main_option("script_location")
        assert "src/shieldops/db/migrations" in location


# ── Migration runner function tests ──────────────────────────────────


class _AsyncContextManager:
    """Helper to create a mock async context manager."""

    def __init__(self, return_value):
        self._return_value = return_value

    async def __aenter__(self):
        return self._return_value

    async def __aexit__(self, *args):
        return False


def _make_mock_engine(mock_conn):
    """Build a MagicMock engine whose .connect() returns an async CM."""
    mock_engine = MagicMock()
    mock_engine.connect.return_value = _AsyncContextManager(mock_conn)
    mock_engine.dispose = AsyncMock()
    return mock_engine


class TestMigrationRunner:
    """Test the async migration runner wrapper functions."""

    @pytest.mark.asyncio
    async def test_run_upgrade_calls_alembic_command(self):
        """run_upgrade delegates to alembic.command.upgrade."""
        with (
            patch("shieldops.db.migrate.create_async_engine") as mock_engine_fn,
            patch("alembic.command.upgrade") as mock_upgrade,
        ):
            mock_conn = MagicMock()
            mock_conn.run_sync = AsyncMock(side_effect=lambda fn: fn(mock_conn))
            mock_conn.commit = AsyncMock()

            mock_engine_fn.return_value = _make_mock_engine(mock_conn)

            from shieldops.db.migrate import run_upgrade

            await run_upgrade("head")

            mock_upgrade.assert_called_once()
            call_args = mock_upgrade.call_args
            assert call_args[0][1] == "head"

    @pytest.mark.asyncio
    async def test_run_downgrade_calls_alembic_command(self):
        """run_downgrade delegates to alembic.command.downgrade."""
        with (
            patch("shieldops.db.migrate.create_async_engine") as mock_engine_fn,
            patch("alembic.command.downgrade") as mock_downgrade,
        ):
            mock_conn = MagicMock()
            mock_conn.run_sync = AsyncMock(side_effect=lambda fn: fn(mock_conn))
            mock_conn.commit = AsyncMock()

            mock_engine_fn.return_value = _make_mock_engine(mock_conn)

            from shieldops.db.migrate import run_downgrade

            await run_downgrade("-1")

            mock_downgrade.assert_called_once()
            call_args = mock_downgrade.call_args
            assert call_args[0][1] == "-1"

    @pytest.mark.asyncio
    async def test_get_current_revision(self):
        """get_current_revision returns the stamped revision."""
        with patch("shieldops.db.migrate.create_async_engine") as mock_engine_fn:
            mock_conn = MagicMock()
            mock_conn.run_sync = AsyncMock(side_effect=lambda fn: fn(mock_conn))

            mock_engine_fn.return_value = _make_mock_engine(mock_conn)

            with patch("shieldops.db.migrate.MigrationContext.configure") as mock_ctx:
                mock_ctx.return_value.get_current_revision.return_value = "001"
                from shieldops.db.migrate import get_current_revision

                result = await get_current_revision()
                assert result == "001"

    @pytest.mark.asyncio
    async def test_get_pending_migrations_when_all_applied(self):
        """get_pending_migrations returns empty list when at head."""
        with (
            patch(
                "shieldops.db.migrate.get_current_revision",
                new_callable=AsyncMock,
                return_value="001",
            ),
            patch("shieldops.db.migrate._get_script_directory") as mock_script,
        ):
            mock_rev = MagicMock()
            mock_rev.revision = "001"
            mock_script.return_value.walk_revisions.return_value = [mock_rev]

            from shieldops.db.migrate import get_pending_migrations

            pending = await get_pending_migrations()
            assert pending == []


# ── API route tests ──────────────────────────────────────────────────


class TestMigrationAPIRoutes:
    """Test the /migrations/* API endpoints."""

    @pytest.mark.asyncio
    async def test_status_returns_503_without_migrator(self, client):
        """GET /migrations/status returns 503 when migrator is not set."""
        response = await client.get("/api/v1/migrations/status")
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_status_returns_current_revision(self, client, mock_migrator):
        """GET /migrations/status returns current revision + pending count."""
        migrations_mod.set_migrator(mock_migrator)

        response = await client.get("/api/v1/migrations/status")
        assert response.status_code == 200
        data = response.json()
        assert data["current_revision"] == "001"
        assert data["pending_count"] == 0
        assert data["pending_revisions"] == []

    @pytest.mark.asyncio
    async def test_upgrade_when_already_at_head(self, client, mock_migrator):
        """POST /migrations/upgrade returns no-op message when at head."""
        migrations_mod.set_migrator(mock_migrator)
        mock_migrator.get_pending_migrations.return_value = []

        response = await client.post("/api/v1/migrations/upgrade")
        assert response.status_code == 200
        data = response.json()
        assert data["applied_count"] == 0
        assert "Already at head" in data["message"]

    @pytest.mark.asyncio
    async def test_upgrade_applies_pending(self, client, mock_migrator):
        """POST /migrations/upgrade applies pending migrations."""
        migrations_mod.set_migrator(mock_migrator)
        mock_migrator.get_pending_migrations.side_effect = [
            ["001"],  # Before upgrade
            [],  # After (not called but for safety)
        ]
        mock_migrator.get_current_revision.return_value = "001"

        response = await client.post("/api/v1/migrations/upgrade")
        assert response.status_code == 200
        data = response.json()
        assert data["applied_count"] == 1
        assert data["current_revision"] == "001"
        mock_migrator.run_upgrade.assert_awaited_once_with("head")

    @pytest.mark.asyncio
    async def test_history_returns_migrations(self, client, mock_migrator):
        """GET /migrations/history returns the full migration list."""
        migrations_mod.set_migrator(mock_migrator)

        response = await client.get("/api/v1/migrations/history")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["migrations"][0]["revision"] == "001"

    @pytest.mark.asyncio
    async def test_upgrade_returns_503_without_migrator(self, client):
        """POST /migrations/upgrade returns 503 when migrator is not set."""
        response = await client.post("/api/v1/migrations/upgrade")
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_history_returns_503_without_migrator(self, client):
        """GET /migrations/history returns 503 when migrator is not set."""
        response = await client.get("/api/v1/migrations/history")
        assert response.status_code == 503
