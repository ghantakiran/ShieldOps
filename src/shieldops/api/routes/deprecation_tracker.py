"""Service deprecation tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.deprecation_tracker import (
    DeprecationImpact,
    DeprecationStage,
    MigrationStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/deprecation-tracker",
    tags=["Deprecation Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Service deprecation tracker service unavailable",
        )
    return _engine


class RecordDeprecationRequest(BaseModel):
    service_name: str
    stage: DeprecationStage = DeprecationStage.ANNOUNCED
    impact: DeprecationImpact = DeprecationImpact.MODERATE
    migration_status: MigrationStatus = MigrationStatus.NOT_STARTED
    eol_date: float = 0.0
    dependent_services: list[str] = []
    details: str = ""


class AddMigrationPlanRequest(BaseModel):
    service_name: str
    target_service: str = ""
    migration_status: MigrationStatus = MigrationStatus.NOT_STARTED
    planned_completion_date: float = 0.0
    owner_team: str = ""
    notes: str = ""


@router.post("/deprecations")
async def record_deprecation(
    body: RecordDeprecationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_deprecation(**body.model_dump())
    return result.model_dump()


@router.get("/deprecations")
async def list_deprecations(
    service_name: str | None = None,
    stage: DeprecationStage | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_deprecations(
            service_name=service_name,
            stage=stage,
            limit=limit,
        )
    ]


@router.get("/deprecations/{record_id}")
async def get_deprecation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_deprecation(record_id)
    if result is None:
        raise HTTPException(404, f"Deprecation record '{record_id}' not found")
    return result.model_dump()


@router.post("/migration-plans")
async def add_migration_plan(
    body: AddMigrationPlanRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_migration_plan(**body.model_dump())
    return result.model_dump()


@router.get("/by-stage")
async def analyze_deprecation_by_stage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_deprecation_by_stage()


@router.get("/overdue-migrations")
async def identify_overdue_migrations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overdue_migrations()


@router.get("/rankings")
async def rank_by_urgency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_urgency()


@router.get("/risks")
async def detect_deprecation_risks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_deprecation_risks()


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


sdt_route = router
