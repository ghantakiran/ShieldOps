"""Capacity Reservation Planner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.capacity_reservation_planner import (
    ReservationTerm,
    ReservationType,
    UtilizationLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/capacity-reservation",
    tags=["Capacity Reservation"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Capacity reservation service unavailable")
    return _engine


class RecordReservationRequest(BaseModel):
    reservation_id: str
    reservation_type: ReservationType = ReservationType.ON_DEMAND
    utilization_level: UtilizationLevel = UtilizationLevel.UNKNOWN
    reservation_term: ReservationTerm = ReservationTerm.ANNUAL
    utilization_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddPlanRequest(BaseModel):
    reservation_id: str
    reservation_type: ReservationType = ReservationType.ON_DEMAND
    plan_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/reservations")
async def record_reservation(
    body: RecordReservationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_reservation(**body.model_dump())
    return result.model_dump()


@router.get("/reservations")
async def list_reservations(
    res_type: ReservationType | None = None,
    level: UtilizationLevel | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_reservations(
            res_type=res_type,
            level=level,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/reservations/{record_id}")
async def get_reservation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_reservation(record_id)
    if result is None:
        raise HTTPException(404, f"Reservation record '{record_id}' not found")
    return result.model_dump()


@router.post("/plans")
async def add_plan(
    body: AddPlanRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_plan(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_reservation_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_reservation_distribution()


@router.get("/under-utilized")
async def identify_under_utilized_reservations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_under_utilized_reservations()


@router.get("/utilization-rankings")
async def rank_by_utilization(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_utilization()


@router.get("/trends")
async def detect_reservation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_reservation_trends()


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


crv_route = router
