"""Evidence scheduler API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
es_route = APIRouter(
    prefix="/evidence-scheduler",
    tags=["Evidence Scheduler"],
)

_instance: Any = None


def set_engine(engine: Any) -> None:
    global _instance
    _instance = engine


def _get_engine() -> Any:
    if _instance is None:
        raise HTTPException(
            503,
            "Evidence scheduler service unavailable",
        )
    return _instance


# -- Request models --


class CreateScheduleRequest(BaseModel):
    evidence_name: str
    framework: str = "soc2"
    frequency: str = "monthly"
    next_due_at: float = 0.0
    owner: str = ""
    description: str = ""


class CreateTaskRequest(BaseModel):
    schedule_id: str
    due_at: float = 0.0


class CompleteTaskRequest(BaseModel):
    task_id: str
    collected_by: str = ""


# -- Routes --


@es_route.post("/schedules")
async def create_schedule(
    body: CreateScheduleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    schedule = engine.create_schedule(**body.model_dump())
    return schedule.model_dump()


@es_route.get("/schedules")
async def list_schedules(
    framework: str | None = None,
    status: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        s.model_dump()
        for s in engine.list_schedules(
            framework=framework,
            status=status,
            limit=limit,
        )
    ]


@es_route.get("/schedules/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    schedule = engine.get_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(404, f"Schedule '{schedule_id}' not found")
    return schedule.model_dump()


@es_route.get("/due-dates")
async def compute_due_dates(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.compute_due_dates()


@es_route.post("/tasks")
async def create_task(
    body: CreateTaskRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    task = engine.create_collection_task(**body.model_dump())
    if task is None:
        raise HTTPException(404, f"Schedule '{body.schedule_id}' not found")
    return task.model_dump()


@es_route.post("/tasks/complete")
async def complete_task(
    body: CompleteTaskRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.complete_task(body.task_id, body.collected_by)
    if not result:
        raise HTTPException(404, f"Task '{body.task_id}' not found")
    return {"completed": True, "task_id": body.task_id}


@es_route.get("/tasks")
async def list_tasks(
    schedule_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        t.model_dump()
        for t in engine.list_tasks(
            schedule_id=schedule_id,
            status=status,
            limit=limit,
        )
    ]


@es_route.get("/overdue")
async def get_overdue(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [s.model_dump() for s in engine.find_overdue_schedules()]


@es_route.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_scheduler_report().model_dump()


@es_route.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
