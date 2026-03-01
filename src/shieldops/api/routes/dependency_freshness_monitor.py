"""Dependency Freshness Monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.dependency_freshness_monitor import (
    DependencyCategory,
    FreshnessLevel,
    UpdateUrgency,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dependency-freshness",
    tags=["Dependency Freshness"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Dependency freshness service unavailable")
    return _engine


class RecordFreshnessRequest(BaseModel):
    dependency_id: str
    freshness_level: FreshnessLevel = FreshnessLevel.CURRENT
    dependency_category: DependencyCategory = DependencyCategory.RUNTIME
    update_urgency: UpdateUrgency = UpdateUrgency.NONE
    versions_behind: int = 0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddCheckRequest(BaseModel):
    dependency_id: str
    freshness_level: FreshnessLevel = FreshnessLevel.CURRENT
    staleness_days: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/freshness")
async def record_freshness(
    body: RecordFreshnessRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_freshness(**body.model_dump())
    return result.model_dump()


@router.get("/freshness")
async def list_freshness(
    level: FreshnessLevel | None = None,
    category: DependencyCategory | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_freshness(
            level=level,
            category=category,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/freshness/{record_id}")
async def get_freshness(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_freshness(record_id)
    if result is None:
        raise HTTPException(404, f"Freshness record '{record_id}' not found")
    return result.model_dump()


@router.post("/checks")
async def add_check(
    body: AddCheckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_check(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_freshness_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_freshness_distribution()


@router.get("/stale-dependencies")
async def identify_stale_dependencies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_stale_dependencies()


@router.get("/staleness-rankings")
async def rank_by_staleness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_staleness()


@router.get("/trends")
async def detect_freshness_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_freshness_trends()


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


dfm_route = router
