"""Platform health index API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.health_index import (
    HealthDimension,
    IndexGrade,
    TrendDirection,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/health-index",
    tags=["Health Index"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Health index service unavailable")
    return _engine


class RecordIndexRequest(BaseModel):
    service_name: str
    dimension: HealthDimension = HealthDimension.AVAILABILITY
    grade: IndexGrade = IndexGrade.GOOD
    trend: TrendDirection = TrendDirection.STABLE
    score_pct: float = 0.0
    details: str = ""


class AddDimensionScoreRequest(BaseModel):
    dimension_name: str
    dimension: HealthDimension = HealthDimension.AVAILABILITY
    grade: IndexGrade = IndexGrade.GOOD
    weight: float = 1.0
    target_score_pct: float = 90.0


@router.post("/indices")
async def record_index(
    body: RecordIndexRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_index(**body.model_dump())
    return result.model_dump()


@router.get("/indices")
async def list_indices(
    service_name: str | None = None,
    dimension: HealthDimension | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_indices(service_name=service_name, dimension=dimension, limit=limit)
    ]


@router.get("/indices/{record_id}")
async def get_index(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_index(record_id)
    if result is None:
        raise HTTPException(404, f"Index '{record_id}' not found")
    return result.model_dump()


@router.post("/dimensions")
async def add_dimension_score(
    body: AddDimensionScoreRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_dimension_score(**body.model_dump())
    return result.model_dump()


@router.get("/platform-health/{service_name}")
async def analyze_platform_health(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_platform_health(service_name)


@router.get("/weak-dimensions")
async def identify_weak_dimensions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_weak_dimensions()


@router.get("/rankings")
async def rank_by_health_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_health_score()


@router.get("/health-trends")
async def detect_health_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_health_trends()


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


phi_route = router
