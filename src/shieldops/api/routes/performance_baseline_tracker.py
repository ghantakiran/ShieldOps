"""Performance Baseline Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.performance_baseline_tracker import (
    BaselineMetric,
    BaselineShift,
    BaselineWindow,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/performance-baseline-tracker",
    tags=["Performance Baseline Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Performance baseline tracker service unavailable")
    return _engine


class RecordBaselineRequest(BaseModel):
    service_name: str
    baseline_metric: BaselineMetric = BaselineMetric.LATENCY_P50
    baseline_shift: BaselineShift = BaselineShift.SIGNIFICANT_IMPROVEMENT
    baseline_window: BaselineWindow = BaselineWindow.HOURLY
    deviation_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddComparisonRequest(BaseModel):
    service_name: str
    baseline_metric: BaselineMetric = BaselineMetric.LATENCY_P50
    comparison_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/baselines")
async def record_baseline(
    body: RecordBaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_baseline(**body.model_dump())
    return result.model_dump()


@router.get("/baselines")
async def list_baselines(
    baseline_metric: BaselineMetric | None = None,
    baseline_shift: BaselineShift | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_baselines(
            baseline_metric=baseline_metric,
            baseline_shift=baseline_shift,
            team=team,
            limit=limit,
        )
    ]


@router.get("/baselines/{record_id}")
async def get_baseline(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_baseline(record_id)
    if result is None:
        raise HTTPException(404, f"Baseline record '{record_id}' not found")
    return result.model_dump()


@router.post("/comparisons")
async def add_comparison(
    body: AddComparisonRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_comparison(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_baseline_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_baseline_distribution()


@router.get("/high-deviations")
async def identify_high_deviations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_deviations()


@router.get("/deviation-rankings")
async def rank_by_deviation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_deviation()


@router.get("/trends")
async def detect_baseline_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_baseline_trends()


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


pbk_route = router
