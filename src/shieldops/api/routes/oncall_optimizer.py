"""On-Call Rotation Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/oncall-optimizer", tags=["On-Call Optimizer"])

_instance: Any = None


def set_optimizer(inst: Any) -> None:
    global _instance
    _instance = inst


def _get_optimizer() -> Any:
    if _instance is None:
        raise HTTPException(503, "On-call optimizer service unavailable")
    return _instance


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RegisterMemberRequest(BaseModel):
    name: str
    email: str = ""
    timezone: str = "UTC"
    skills: list[str] = Field(default_factory=list)


class GenerateScheduleRequest(BaseModel):
    strategy: str
    member_ids: list[str]
    start_date: str = ""
    end_date: str = ""


class TrackLoadRequest(BaseModel):
    member_id: str
    hours: float = 0.0
    pages: int = 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/members")
async def register_member(
    body: RegisterMemberRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    result = optimizer.register_member(
        name=body.name,
        email=body.email,
        timezone=body.timezone,
        skills=body.skills,
    )
    return result.model_dump()


@router.get("/members")
async def list_members(
    timezone: str | None = None,
    is_available: bool | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [
        m.model_dump()
        for m in optimizer.list_members(
            timezone=timezone,
            is_available=is_available,
            limit=limit,
        )
    ]


@router.get("/members/{member_id}")
async def get_member(
    member_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    result = optimizer.get_member(member_id)
    if result is None:
        raise HTTPException(404, f"Member '{member_id}' not found")
    return result.model_dump()


@router.post("/schedules")
async def generate_schedule(
    body: GenerateScheduleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    result = optimizer.generate_schedule(
        strategy=body.strategy,
        member_ids=body.member_ids,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    return result.model_dump()


@router.get("/schedules/{schedule_id}/fairness")
async def calculate_fairness(
    schedule_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.calculate_fairness_score(schedule_id)


@router.get("/coverage-gaps")
async def detect_coverage_gaps(
    schedule_id: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[str]:
    optimizer = _get_optimizer()
    return optimizer.detect_coverage_gaps(schedule_id=schedule_id)


@router.get("/handoffs")
async def optimize_handoffs(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return optimizer.optimize_handoffs()


@router.post("/track-load")
async def track_load(
    body: TrackLoadRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    result = optimizer.track_actual_load(
        member_id=body.member_id,
        hours=body.hours,
        pages=body.pages,
    )
    if result is None:
        raise HTTPException(404, f"Member '{body.member_id}' not found")
    return result.model_dump()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.generate_rotation_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.get_stats()
