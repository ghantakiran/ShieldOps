"""Async-compatible migration runner wrapping Alembic's command API.

Provides programmatic access to common migration operations (upgrade,
downgrade, status checks) so they can be invoked from application code
or API endpoints without shelling out to the ``alembic`` CLI.
"""

from __future__ import annotations

from pathlib import Path

import structlog
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from shieldops.config import settings

logger = structlog.get_logger()

_MIGRATIONS_DIR = str(Path(__file__).resolve().parent / "migrations")


def _make_alembic_config() -> Config:
    """Build an Alembic Config pointing at the migrations directory."""
    cfg = Config()
    cfg.set_main_option("script_location", _MIGRATIONS_DIR)
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def _get_script_directory() -> ScriptDirectory:
    """Return the Alembic ScriptDirectory for the project migrations."""
    return ScriptDirectory.from_config(_make_alembic_config())


async def run_upgrade(revision: str = "head") -> None:
    """Apply migrations up to *revision* (default: ``head``).

    Connects to the database using an async engine and runs the upgrade
    within a synchronous callback (required by Alembic's API).
    """
    from alembic import command  # type: ignore[attr-defined]

    logger.info("migration_upgrade_start", target_revision=revision)

    cfg = _make_alembic_config()

    engine = create_async_engine(settings.database_url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as conn:

            def _do_upgrade(connection) -> None:  # type: ignore[no-untyped-def]
                cfg.attributes["connection"] = connection
                command.upgrade(cfg, revision)

            await conn.run_sync(_do_upgrade)
            await conn.commit()
    finally:
        await engine.dispose()

    logger.info("migration_upgrade_complete", target_revision=revision)


async def run_downgrade(revision: str = "-1") -> None:
    """Roll back migrations to *revision* (default: one step back).

    Uses the same async engine pattern as :func:`run_upgrade`.
    """
    from alembic import command  # type: ignore[attr-defined]

    logger.info("migration_downgrade_start", target_revision=revision)

    cfg = _make_alembic_config()

    engine = create_async_engine(settings.database_url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as conn:

            def _do_downgrade(connection) -> None:  # type: ignore[no-untyped-def]
                cfg.attributes["connection"] = connection
                command.downgrade(cfg, revision)

            await conn.run_sync(_do_downgrade)
            await conn.commit()
    finally:
        await engine.dispose()

    logger.info("migration_downgrade_complete", target_revision=revision)


async def get_current_revision() -> str | None:
    """Return the current migration revision stamped in the database.

    Returns ``None`` if no ``alembic_version`` table exists yet (i.e.
    migrations have never been applied).
    """
    engine = create_async_engine(settings.database_url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as conn:

            def _get_rev(connection) -> str | None:  # type: ignore[no-untyped-def]
                ctx = MigrationContext.configure(connection)
                result: str | None = ctx.get_current_revision()
                return result

            rev: str | None = await conn.run_sync(_get_rev)
            return rev
    finally:
        await engine.dispose()


async def get_pending_migrations() -> list[str]:
    """Return a list of revision identifiers that have not been applied yet.

    Compares the current DB revision against all known migration scripts
    and returns the revisions between the current state and head.
    """
    current = await get_current_revision()
    script = _get_script_directory()

    pending: list[str] = []
    for rev in script.walk_revisions("head", "base"):
        pending.append(rev.revision)
        if rev.revision == current:
            break

    # If current is None (no migrations applied), all are pending.
    # If current is head, nothing is pending (the loop collected up to head).
    if current is not None and pending and pending[-1] == current:
        pending.pop()  # Remove current -- it is already applied.

    pending.reverse()
    return pending


async def get_migration_history() -> list[dict[str, str | None]]:
    """Return all known migration revisions with their metadata.

    Each entry includes ``revision``, ``down_revision``, and ``doc``
    (the migration's docstring / message).
    """
    script = _get_script_directory()
    history: list[dict[str, str | None]] = []
    for rev in script.walk_revisions("head", "base"):
        history.append(
            {
                "revision": rev.revision,
                "down_revision": (
                    rev.down_revision if isinstance(rev.down_revision, str) else None
                ),
                "description": rev.doc,
            }
        )
    history.reverse()
    return history
