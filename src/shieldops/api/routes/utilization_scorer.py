"""Capacity utilization scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.utilization_scorer import (
    ResourceType,
    UtilizationGrade,
    UtilizationTrend,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/utilization-scorer",
    tags=["Utilization Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Utilization scorer service unavailable")
    return _engine


class RecordUtilizationRequest(BaseModel):
    resource_name: str
    resource_type: ResourceType = ResourceType.CPU
    utilization_pct: float = 0.0
    grade: UtilizationGrade = UtilizationGrade.GOOD
    trend: UtilizationTrend = UtilizationTrend.INSUFFICIENT_DATA
    environment: str = ""


class AddMetricRequest(BaseModel):
    metric_name: str
    resource_type: ResourceType = ResourceType.CPU
    threshold_pct: float = 0.0
    sample_window_minutes: int = 60
    environment: str = ""


@router.post("/utilizations")
async def record_utilization(
    body: RecordUtilizationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_utilization(**body.model_dump())
    return result.model_dump()


@router.get("/utilizations")
async def list_utilizations(
    resource_type: ResourceType | None = None,
    grade: UtilizationGrade | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_utilizations(resource_type=resource_type, grade=grade, limit=limit)
    ]


@router.get("/utilizations/{record_id}")
async def get_utilization(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_utilization(record_id)
    if result is None:
        raise HTTPException(404, f"Utilization record '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{resource_type}")
async def analyze_utilization_by_resource(
    resource_type: ResourceType,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_utilization_by_resource(resource_type)


@router.get("/over-provisioned")
async def identify_over_provisioned(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_over_provisioned()


@router.get("/rankings")
async def rank_by_utilization_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_utilization_score()


@router.get("/trends")
async def detect_utilization_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_utilization_trends()


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


cus_route = router
