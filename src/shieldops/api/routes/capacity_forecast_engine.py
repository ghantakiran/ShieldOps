"""Capacity forecast engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/capacity-forecast-engine",
    tags=["Capacity Forecast Engine"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Capacity forecast engine service unavailable",
        )
    return _engine


# -- Request models -------------------------------------------------


class IngestUsageRequest(BaseModel):
    service_name: str
    dimension: str = "CPU"
    value: float = 0.0
    capacity_limit: float = 100.0
    recorded_at: float | None = None


class GenerateForecastRequest(BaseModel):
    service_name: str
    dimension: str = "CPU"
    method: str = "LINEAR"


class PlanHeadroomRequest(BaseModel):
    target_utilization_pct: float = 70.0


# -- Routes ---------------------------------------------------------


@router.post("/usage")
async def ingest_usage(
    body: IngestUsageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    dp = eng.ingest_usage(**body.model_dump())
    return dp.model_dump()


@router.get("/usage")
async def list_usage(
    service_name: str | None = None,
    dimension: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    eng = _get_engine()
    return [
        d.model_dump()
        for d in eng.list_usage(
            service_name=service_name,
            dimension=dimension,
            limit=limit,
        )
    ]


@router.get("/usage/{dp_id}")
async def get_data_point(
    dp_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    dp = eng.get_data_point(dp_id)
    if dp is None:
        raise HTTPException(404, f"Data point '{dp_id}' not found")
    return dp.model_dump()


@router.post("/forecasts")
async def generate_forecast(
    body: GenerateForecastRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    fc = eng.generate_forecast(**body.model_dump())
    return fc.model_dump()


@router.get("/capacity-risk")
async def detect_capacity_risk(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    eng = _get_engine()
    return eng.detect_capacity_risk()


@router.get("/days-to-exhaustion")
async def calculate_days_to_exhaustion(
    service_name: str = "",
    dimension: str = "CPU",
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    days = eng.calculate_days_to_exhaustion(service_name, dimension)
    return {
        "service_name": service_name,
        "dimension": dimension,
        "days": days,
    }


@router.get("/trending")
async def identify_trending_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    eng = _get_engine()
    return eng.identify_trending_services()


@router.post("/headroom")
async def plan_headroom(
    body: PlanHeadroomRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    eng = _get_engine()
    return eng.plan_headroom(**body.model_dump())


@router.get("/report")
async def generate_forecast_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    return eng.generate_forecast_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    eng = _get_engine()
    return eng.get_stats()
