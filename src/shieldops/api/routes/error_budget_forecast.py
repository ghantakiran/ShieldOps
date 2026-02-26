"""Error budget forecaster API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.error_budget_forecast import (
    BudgetStatus,
    BurnRate,
    ForecastHorizon,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/error-budget-forecast",
    tags=["Error Budget Forecast"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Error budget forecast service unavailable")
    return _engine


class RecordSnapshotRequest(BaseModel):
    slo_name: str
    budget_remaining_pct: float = 100.0
    burn_rate: BurnRate = BurnRate.NORMAL
    status: BudgetStatus | None = None
    error_count: int = 0
    total_requests: int = 0
    details: str = ""


class CreateForecastRequest(BaseModel):
    slo_name: str
    horizon: ForecastHorizon = ForecastHorizon.ONE_WEEK
    projected_remaining_pct: float = 0.0
    exhaustion_days: float = 0.0
    confidence_pct: float = 0.0


@router.post("/snapshots")
async def record_snapshot(
    body: RecordSnapshotRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_snapshot(**body.model_dump())
    return result.model_dump()


@router.get("/snapshots")
async def list_snapshots(
    slo_name: str | None = None,
    status: BudgetStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump() for r in engine.list_snapshots(slo_name=slo_name, status=status, limit=limit)
    ]


@router.get("/snapshots/{record_id}")
async def get_snapshot(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_snapshot(record_id)
    if result is None:
        raise HTTPException(404, f"Snapshot '{record_id}' not found")
    return result.model_dump()


@router.post("/forecasts")
async def create_forecast(
    body: CreateForecastRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.create_forecast(**body.model_dump())
    return result.model_dump()


@router.get("/health/{slo_name}")
async def analyze_budget_health(
    slo_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_budget_health(slo_name)


@router.get("/at-risk")
async def identify_at_risk_budgets(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_at_risk_budgets()


@router.get("/rankings")
async def rank_by_burn_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_burn_rate()


@router.get("/exhaustion-timeline")
async def project_exhaustion_timeline(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.project_exhaustion_timeline()


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


ebf_route = router
