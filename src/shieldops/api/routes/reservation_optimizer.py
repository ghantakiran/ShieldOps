"""Reservation Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.reservation_optimizer import (
    ReservationAction,
    ReservationType,
    UtilizationLevel,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/reservation-optimizer", tags=["Reservation Optimizer"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Reservation optimizer service unavailable")
    return _engine


class RecordReservationRequest(BaseModel):
    reservation_id: str
    reservation_type: ReservationType = ReservationType.COMPUTE
    utilization_level: UtilizationLevel = UtilizationLevel.OPTIMAL
    reservation_action: ReservationAction = ReservationAction.KEEP
    utilization_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    reservation_id: str
    reservation_type: ReservationType = ReservationType.COMPUTE
    metric_value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_reservation(
    body: RecordReservationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_reservation(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_reservations(
    reservation_type: ReservationType | None = None,
    utilization: UtilizationLevel | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_reservations(
            reservation_type=reservation_type,
            utilization=utilization,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_reservation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_reservation(record_id)
    if result is None:
        raise HTTPException(404, f"Reservation record '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_utilization(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_utilization()


@router.get("/underutilized")
async def identify_underutilized_reservations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_underutilized_reservations()


@router.get("/utilization-rankings")
async def rank_by_utilization(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_utilization()


@router.get("/trends")
async def detect_utilization_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
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


rvo_route = router
