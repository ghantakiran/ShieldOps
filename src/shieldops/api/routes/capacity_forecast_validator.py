"""Capacity Forecast Validator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.capacity_forecast_validator import (
    ForecastAccuracy,
    ForecastBias,
    ForecastMethod,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/capacity-forecast-validator",
    tags=["Capacity Forecast Validator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Capacity forecast validator service unavailable")
    return _engine


class RecordValidationRequest(BaseModel):
    forecast_id: str
    forecast_accuracy: ForecastAccuracy = ForecastAccuracy.ACCEPTABLE
    forecast_bias: ForecastBias = ForecastBias.BALANCED
    forecast_method: ForecastMethod = ForecastMethod.LINEAR
    accuracy_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddCheckRequest(BaseModel):
    forecast_id: str
    forecast_accuracy: ForecastAccuracy = ForecastAccuracy.ACCEPTABLE
    check_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/validations")
async def record_validation(
    body: RecordValidationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_validation(**body.model_dump())
    return result.model_dump()


@router.get("/validations")
async def list_validations(
    accuracy: ForecastAccuracy | None = None,
    bias: ForecastBias | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_validations(
            accuracy=accuracy,
            bias=bias,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/validations/{record_id}")
async def get_validation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_validation(record_id)
    if result is None:
        raise HTTPException(404, f"Validation '{record_id}' not found")
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
async def analyze_forecast_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_forecast_distribution()


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
async def detect_forecast_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_forecast_trends()


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


cfx_route = router
