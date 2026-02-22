"""Migration management API routes (admin only).

Provides endpoints for checking migration status, applying pending
migrations, and viewing migration history. All endpoints require
the ``admin`` role.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from shieldops.api.auth.dependencies import require_role
from shieldops.api.auth.models import UserResponse, UserRole

logger = structlog.get_logger()

router = APIRouter(prefix="/migrations", tags=["Migrations"])

# Module-level singleton -- injected at startup via set_migrator().
_migrator: Any | None = None


def set_migrator(migrator: Any) -> None:
    """Inject the migration module (or compatible duck-typed object).

    Called during application startup to wire the ``shieldops.db.migrate``
    module into these route handlers.
    """
    global _migrator
    _migrator = migrator


def _get_migrator() -> Any:
    """Return the active migrator or raise 503."""
    if _migrator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Migration service not initialized",
        )
    return _migrator


@router.get("/status")
async def migration_status(
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Return the current migration revision and count of pending migrations."""
    migrator = _get_migrator()
    current = await migrator.get_current_revision()
    pending = await migrator.get_pending_migrations()
    return {
        "current_revision": current,
        "pending_count": len(pending),
        "pending_revisions": pending,
    }


@router.post("/upgrade")
async def migration_upgrade(
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Apply all pending migrations up to head."""
    migrator = _get_migrator()
    pending_before = await migrator.get_pending_migrations()

    if not pending_before:
        return {"message": "Already at head", "applied_count": 0}

    await migrator.run_upgrade("head")

    current = await migrator.get_current_revision()
    logger.info(
        "migrations_applied_via_api",
        applied_count=len(pending_before),
        new_revision=current,
    )
    return {
        "message": "Migrations applied successfully",
        "applied_count": len(pending_before),
        "current_revision": current,
    }


@router.get("/history")
async def migration_history(
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Return the full list of known migration revisions."""
    migrator = _get_migrator()
    history = await migrator.get_migration_history()
    return {"migrations": history, "total": len(history)}
