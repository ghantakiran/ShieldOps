"""Workload scheduler optimization API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/workload-scheduler", tags=["Workload Scheduler"])

_optimizer: Any = None


def set_optimizer(optimizer: Any) -> None:
    global _optimizer
    _optimizer = optimizer


def _get_optimizer() -> Any:
    if _optimizer is None:
        raise HTTPException(503, "Workload scheduler service unavailable")
    return _optimizer


class RegisterWorkloadRequest(BaseModel):
    workload_name: str
    priority: str = "MEDIUM"
    strategy: str = "BALANCED"
    scheduled_start: float = 0.0
    duration_seconds: int = 3600
    resource_requirements: dict[str, Any] | None = None
    estimated_cost: float = 0.0


class UpdateScheduleRequest(BaseModel):
    scheduled_start: float | None = None
    duration_seconds: int | None = None
    strategy: str | None = None


@router.post("/workloads")
async def register_workload(
    body: RegisterWorkloadRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    workload = optimizer.register_workload(**body.model_dump())
    return workload.model_dump()


@router.get("/workloads")
async def list_workloads(
    priority: str | None = None,
    strategy: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [
        w.model_dump()
        for w in optimizer.list_workloads(priority=priority, strategy=strategy, limit=limit)
    ]


@router.get("/workloads/{workload_id}")
async def get_workload(
    workload_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    workload = optimizer.get_workload(workload_id)
    if workload is None:
        raise HTTPException(404, f"Workload '{workload_id}' not found")
    return workload.model_dump()


@router.put("/workloads/{workload_id}/schedule")
async def update_workload_schedule(
    workload_id: str,
    body: UpdateScheduleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    workload = optimizer.update_workload_schedule(workload_id=workload_id, **body.model_dump())
    if not workload:
        raise HTTPException(404, f"Workload '{workload_id}' not found")
    return workload.model_dump()


@router.get("/conflicts")
async def detect_conflicts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [c.model_dump() for c in optimizer.detect_conflicts()]


@router.get("/peak-windows")
async def analyze_peak_windows(
    window_hours: int = 1,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.analyze_peak_windows(window_hours=window_hours)


@router.get("/schedule-shifts")
async def recommend_schedule_shifts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [s.model_dump() for s in optimizer.recommend_schedule_shifts()]


@router.get("/cost-savings")
async def estimate_cost_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.estimate_cost_savings()


@router.get("/optimization-report")
async def generate_optimization_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.generate_optimization_report()


@router.delete("/workloads/{workload_id}")
async def delete_workload(
    workload_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    removed = optimizer.delete_workload(workload_id)
    if not removed:
        raise HTTPException(404, f"Workload '{workload_id}' not found")
    return {"deleted": True, "workload_id": workload_id}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.get_stats()
