"""SLO compliance forecaster API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_forecast import ForecastHorizon

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-forecast",
    tags=["SLO Forecast"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "SLO forecast service unavailable",
        )
    return _engine


class RecordMeasurementRequest(BaseModel):
    service: str
    slo_name: str
    target_pct: float = 99.9
    current_pct: float = 100.0
    horizon: ForecastHorizon = ForecastHorizon.MONTHLY
    period_elapsed_pct: float = 0.0


class ForecastRequest(BaseModel):
    service: str
    slo_name: str


@router.post("/measurements")
async def record_measurement(
    body: RecordMeasurementRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_measurement(**body.model_dump())
    return result.model_dump()


@router.get("/measurements")
async def list_measurements(
    service: str | None = None,
    slo_name: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_measurements(service=service, slo_name=slo_name, limit=limit)
    ]


@router.get("/measurements/{measurement_id}")
async def get_measurement(
    measurement_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_measurement(measurement_id)
    if result is None:
        raise HTTPException(404, f"Measurement '{measurement_id}' not found")
    return result.model_dump()


@router.post("/forecast")
async def forecast_compliance(
    body: ForecastRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.forecast_compliance(body.service, body.slo_name)
    return result.model_dump()


@router.get("/risk/{service}/{slo_name}")
async def assess_risk(
    service: str,
    slo_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.assess_risk(service, slo_name)


@router.get("/at-risk")
async def identify_at_risk_slos(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_at_risk_slos()


@router.get("/project/{service}/{slo_name}")
async def project_end_of_period(
    service: str,
    slo_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.project_end_of_period(service, slo_name)


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


sf_route = router
