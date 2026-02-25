"""API version health monitor routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.api_version_health import (
    MigrationProgress,
    VersionStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/api-version-health",
    tags=["API Version Health"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "API version health service unavailable")
    return _engine


class RecordVersionRequest(BaseModel):
    api_name: str
    version: str
    status: VersionStatus = VersionStatus.CURRENT
    consumer_count: int = 0
    sunset_days_remaining: int = -1
    traffic_pct: float = 0.0
    details: str = ""


class RecordMigrationRequest(BaseModel):
    api_name: str
    from_version: str
    to_version: str
    progress: MigrationProgress = MigrationProgress.NOT_STARTED
    consumer_migrated_pct: float = 0.0
    details: str = ""


@router.post("/versions")
async def record_version(
    body: RecordVersionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_version(**body.model_dump())
    return result.model_dump()


@router.get("/versions")
async def list_versions(
    api_name: str | None = None,
    status: VersionStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump() for r in engine.list_versions(api_name=api_name, status=status, limit=limit)
    ]


@router.get("/versions/{record_id}")
async def get_version(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_version(record_id)
    if result is None:
        raise HTTPException(404, f"Version record '{record_id}' not found")
    return result.model_dump()


@router.post("/migrations")
async def record_migration(
    body: RecordMigrationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_migration(**body.model_dump())
    return result.model_dump()


@router.get("/sunset-risks")
async def identify_sunset_risks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_sunset_risks()


@router.get("/migration-progress")
async def track_migration_progress(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.track_migration_progress()


@router.get("/zombies")
async def identify_zombie_versions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_zombie_versions()


@router.get("/rankings")
async def rank_apis_by_version_health(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_apis_by_version_health()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.clear_data()


avh_route = router
