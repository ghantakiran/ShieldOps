"""API deprecation tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/api-deprecation-tracker", tags=["API Deprecation Tracker"])

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "API deprecation tracker service unavailable")
    return _tracker


class RegisterAPIVersionRequest(BaseModel):
    api_name: str
    version: str
    stage: str = "ACTIVE"
    deprecated_at: float = 0.0
    sunset_date: float = 0.0
    replacement_version: str = ""
    consumer_count: int = 0


class RegisterConsumerMigrationRequest(BaseModel):
    api_version_id: str
    consumer_name: str


class UpdateMigrationStatusRequest(BaseModel):
    status: str
    notes: str = ""


@router.post("/api-versions")
async def register_api_version(
    body: RegisterAPIVersionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    version = tracker.register_api_version(**body.model_dump())
    return version.model_dump()


@router.get("/api-versions")
async def list_api_versions(
    stage: str | None = None,
    api_name: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [
        v.model_dump()
        for v in tracker.list_api_versions(stage=stage, api_name=api_name, limit=limit)
    ]


@router.get("/api-versions/{version_id}")
async def get_api_version(
    version_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    version = tracker.get_api_version(version_id)
    if version is None:
        raise HTTPException(404, f"API version '{version_id}' not found")
    return version.model_dump()


@router.post("/migrations")
async def register_consumer_migration(
    body: RegisterConsumerMigrationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    migration = tracker.register_consumer_migration(**body.model_dump())
    return migration.model_dump()


@router.put("/migrations/{migration_id}/status")
async def update_migration_status(
    migration_id: str,
    body: UpdateMigrationStatusRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    updated = tracker.update_migration_status(migration_id, **body.model_dump())
    if not updated:
        raise HTTPException(404, f"Migration '{migration_id}' not found")
    return {"updated": True, "migration_id": migration_id}


@router.get("/overdue-sunsets")
async def detect_overdue_sunsets(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [v.model_dump() for v in tracker.detect_overdue_sunsets()]


@router.get("/migration-progress/{api_version_id}")
async def calculate_migration_progress(
    api_version_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.calculate_migration_progress(api_version_id)


@router.get("/urgency/{api_version_id}")
async def assess_deprecation_urgency(
    api_version_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.assess_deprecation_urgency(api_version_id)


@router.get("/report")
async def generate_deprecation_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.generate_deprecation_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
