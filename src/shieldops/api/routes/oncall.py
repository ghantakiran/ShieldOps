"""On-call schedule API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role
from shieldops.integrations.oncall.schedule import RotationType

logger = structlog.get_logger()
router = APIRouter(prefix="/oncall", tags=["On-Call"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "On-call service unavailable")
    return _manager


class CreateScheduleRequest(BaseModel):
    name: str
    users: list[str]
    team: str = ""
    timezone: str = "UTC"
    rotation_type: RotationType | None = None
    rotation_interval_hours: float | None = None
    handoff_time_hour: int = 9
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddOverrideRequest(BaseModel):
    user: str
    start_time: float
    end_time: float
    reason: str = ""
    created_by: str = ""


class ShiftRangeRequest(BaseModel):
    start_time: float
    end_time: float


@router.post("/schedules")
async def create_schedule(
    body: CreateScheduleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    schedule = mgr.create_schedule(**body.model_dump())
    return schedule.model_dump()


@router.get("/schedules")
async def list_schedules(
    team: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [s.model_dump() for s in mgr.list_schedules(team=team)]


@router.get("/schedules/{schedule_id}/current")
async def get_current_oncall(
    schedule_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    schedule = mgr.get_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(404, f"Schedule '{schedule_id}' not found")
    current = mgr.get_current_oncall(schedule_id)
    return {"schedule_id": schedule_id, "current_oncall": current}


@router.get("/schedules/{schedule_id}/shifts")
async def get_shifts(
    schedule_id: str,
    start_time: float = 0,
    end_time: float = 0,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    import time

    s = start_time or time.time()
    e = end_time or (s + 604800)
    return [sh.model_dump() for sh in mgr.get_schedule_for_range(schedule_id, s, e)]


@router.post("/schedules/{schedule_id}/overrides")
async def add_override(
    schedule_id: str,
    body: AddOverrideRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    override = mgr.add_override(schedule_id, **body.model_dump())
    if override is None:
        raise HTTPException(404, f"Schedule '{schedule_id}' not found")
    return override.model_dump()


@router.get("/who-is-oncall")
async def who_is_oncall(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    result = []
    for schedule in mgr.list_schedules():
        current = mgr.get_current_oncall(schedule.id)
        result.append(
            {
                "schedule_id": schedule.id,
                "schedule_name": schedule.name,
                "team": schedule.team,
                "current_oncall": current,
            }
        )
    return result
