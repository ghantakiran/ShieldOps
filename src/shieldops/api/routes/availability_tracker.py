"""Platform availability tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.availability_tracker import (
    AvailabilityStatus,
    OutageCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/availability-tracker",
    tags=["Availability Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Availability tracker service unavailable",
        )
    return _engine


class RecordAvailabilityRequest(BaseModel):
    model_config = {"extra": "forbid"}

    service: str
    availability_pct: float = 100.0
    status: AvailabilityStatus = AvailabilityStatus.FULLY_AVAILABLE
    outage_minutes: float = 0.0
    category: OutageCategory = OutageCategory.INFRASTRUCTURE
    team: str = ""
    details: str = ""


class AddOutageRequest(BaseModel):
    model_config = {"extra": "forbid"}

    service: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_minutes: float = 0.0
    category: OutageCategory = OutageCategory.INFRASTRUCTURE
    root_cause: str = ""


@router.post("/availabilities")
async def record_availability(
    body: RecordAvailabilityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_availability(**body.model_dump())
    return result.model_dump()


@router.get("/availabilities")
async def list_availabilities(
    status: AvailabilityStatus | None = None,
    category: OutageCategory | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_availabilities(
            status=status,
            category=category,
            team=team,
            limit=limit,
        )
    ]


@router.get("/availabilities/{record_id}")
async def get_availability(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_availability(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Availability '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/outages")
async def add_outage(
    body: AddOutageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_outage(**body.model_dump())
    return result.model_dump()


@router.get("/by-service")
async def analyze_availability_by_service(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_availability_by_service()


@router.get("/below-target")
async def identify_below_target_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_below_target_services()


@router.get("/rankings")
async def rank_by_availability(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_availability()


@router.get("/trends")
async def detect_availability_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_availability_trends()


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


pat_route = router
