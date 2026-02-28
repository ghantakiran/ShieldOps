"""Cost efficiency scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.cost_efficiency import (
    EfficiencyCategory,
    EfficiencyGrade,
    OptimizationPotential,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cost-efficiency",
    tags=["Cost Efficiency"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cost efficiency scorer service unavailable")
    return _engine


class RecordEfficiencyRequest(BaseModel):
    service_name: str
    category: EfficiencyCategory = EfficiencyCategory.COMPUTE
    grade: EfficiencyGrade | None = None
    potential: OptimizationPotential = OptimizationPotential.MODERATE
    efficiency_pct: float = 0.0
    monthly_cost: float = 0.0
    wasted_spend: float = 0.0
    details: str = ""


class AddMetricRequest(BaseModel):
    service_name: str
    category: EfficiencyCategory = EfficiencyCategory.COMPUTE
    metric_name: str = ""
    value: float = 0.0
    unit: str = ""


@router.post("/efficiencies")
async def record_efficiency(
    body: RecordEfficiencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_efficiency(**body.model_dump())
    return result.model_dump()


@router.get("/efficiencies")
async def list_efficiencies(
    service_name: str | None = None,
    category: EfficiencyCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_efficiencies(
            service_name=service_name,
            category=category,
            limit=limit,
        )
    ]


@router.get("/efficiencies/{record_id}")
async def get_efficiency(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_efficiency(record_id)
    if result is None:
        raise HTTPException(404, f"Efficiency record '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/service/{service_name}")
async def analyze_efficiency_by_service(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_efficiency_by_service(service_name)


@router.get("/wasteful")
async def identify_wasteful_resources(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_wasteful_resources()


@router.get("/rankings")
async def rank_by_efficiency_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_efficiency_score()


@router.get("/trends")
async def detect_efficiency_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_efficiency_trends()


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


ces_route = router
