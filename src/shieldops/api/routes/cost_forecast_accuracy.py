"""Cost Forecast Accuracy Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.cost_forecast_accuracy import (
    AccuracyGrade,
    DeviationCause,
    ForecastHorizon,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cost-forecast-accuracy",
    tags=["Cost Forecast Accuracy"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cost forecast accuracy service unavailable")
    return _engine


class RecordForecastRequest(BaseModel):
    forecast_id: str
    forecast_horizon: ForecastHorizon = ForecastHorizon.MONTHLY
    accuracy_grade: AccuracyGrade = AccuracyGrade.FAIR
    deviation_cause: DeviationCause = DeviationCause.ANOMALY
    accuracy_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddEvaluationRequest(BaseModel):
    forecast_id: str
    forecast_horizon: ForecastHorizon = ForecastHorizon.MONTHLY
    eval_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/forecasts")
async def record_forecast(
    body: RecordForecastRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_forecast(**body.model_dump())
    return result.model_dump()


@router.get("/forecasts")
async def list_forecasts(
    horizon: ForecastHorizon | None = None,
    grade: AccuracyGrade | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_forecasts(
            horizon=horizon,
            grade=grade,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/forecasts/{record_id}")
async def get_forecast(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_forecast(record_id)
    if result is None:
        raise HTTPException(404, f"Forecast record '{record_id}' not found")
    return result.model_dump()


@router.post("/evaluations")
async def add_evaluation(
    body: AddEvaluationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_evaluation(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_accuracy_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_accuracy_distribution()


@router.get("/inaccurate")
async def identify_inaccurate_forecasts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_inaccurate_forecasts()


@router.get("/accuracy-rankings")
async def rank_by_accuracy(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_accuracy()


@router.get("/trends")
async def detect_accuracy_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_accuracy_trends()


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


cfa_route = router
