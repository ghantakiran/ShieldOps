"""Configuration audit trail API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/config-audit",
    tags=["Config Audit"],
)

_trail: Any = None


def set_trail(trail: Any) -> None:
    global _trail
    _trail = trail


def _get_trail() -> Any:
    if _trail is None:
        raise HTTPException(503, "Config audit service unavailable")
    return _trail


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordChangeRequest(BaseModel):
    config_key: str
    value: str
    changed_by: str = ""
    scope: str = "service"
    reason: str = ""


class RestoreVersionRequest(BaseModel):
    version: int
    restored_by: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/changes")
async def record_change(
    body: RecordChangeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    trail = _get_trail()
    entry = trail.record_change(
        config_key=body.config_key,
        value=body.value,
        changed_by=body.changed_by,
        scope=body.scope,
        reason=body.reason,
    )
    return entry.model_dump()


@router.get("/current")
async def get_current(
    config_key: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    trail = _get_trail()
    entry = trail.get_current(config_key)
    if entry is None:
        raise HTTPException(404, f"Config key '{config_key}' not found")
    return entry.model_dump()


@router.get("/history")
async def get_history(
    config_key: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    trail = _get_trail()
    return [e.model_dump() for e in trail.get_history(config_key)]


@router.get("/diff")
async def get_diff(
    config_key: str,
    from_version: int,
    to_version: int,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    trail = _get_trail()
    diff = trail.get_diff(config_key, from_version, to_version)
    if diff is None:
        raise HTTPException(404, "Version not found")
    return diff.model_dump()


@router.post("/restore")
async def restore_version(
    config_key: str,
    body: RestoreVersionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    trail = _get_trail()
    entry = trail.restore_version(config_key, body.version, body.restored_by)
    if entry is None:
        raise HTTPException(404, "Version not found")
    return entry.model_dump()


@router.get("/blame")
async def blame(
    config_key: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    trail = _get_trail()
    return trail.blame(config_key)


@router.get("/search")
async def search(
    query: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    trail = _get_trail()
    return [e.model_dump() for e in trail.search(query)]


@router.get("/recent")
async def list_recent(
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    trail = _get_trail()
    return [e.model_dump() for e in trail.list_recent_changes(limit=limit)]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    trail = _get_trail()
    return trail.get_stats()
