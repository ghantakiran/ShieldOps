"""Secret Rotation Planner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.secret_rotation_planner import (
    RotationRisk,
    RotationStatus,
    SecretType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/secret-rotation", tags=["Secret Rotation"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Secret rotation planner service unavailable")
    return _engine


class RecordRotationRequest(BaseModel):
    secret_id: str
    secret_type: SecretType = SecretType.API_KEY  # noqa: S105
    rotation_status: RotationStatus = RotationStatus.ON_SCHEDULE
    rotation_risk: RotationRisk = RotationRisk.LOW
    days_until_rotation: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddScheduleRequest(BaseModel):
    secret_id: str
    secret_type: SecretType = SecretType.API_KEY  # noqa: S105
    schedule_days: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_rotation(
    body: RecordRotationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_rotation(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_rotations(
    secret_type: SecretType | None = None,
    status: RotationStatus | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_rotations(
            secret_type=secret_type,
            status=status,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_rotation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_rotation(record_id)
    if result is None:
        raise HTTPException(404, f"Rotation record '{record_id}' not found")
    return result.model_dump()


@router.post("/schedules")
async def add_schedule(
    body: AddScheduleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_schedule(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_rotation_compliance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_rotation_compliance()


@router.get("/overdue")
async def identify_overdue_rotations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overdue_rotations()


@router.get("/urgency-rankings")
async def rank_by_urgency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_urgency()


@router.get("/trends")
async def detect_rotation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_rotation_trends()


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


srp_route = router
