"""SLA violation tracking API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/sla-violations", tags=["SLA Violations"])

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "SLA violation service unavailable")
    return _tracker


class CreateTargetRequest(BaseModel):
    service: str
    metric_type: str
    target_value: float
    threshold_warning: float
    threshold_breach: float
    period_hours: int = 24
    metadata: dict[str, Any] = Field(default_factory=dict)


class CheckViolationRequest(BaseModel):
    target_id: str
    current_value: float


@router.post("/targets")
async def create_target(
    body: CreateTargetRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    target = tracker.create_target(**body.model_dump())
    return target.model_dump()


@router.get("/targets")
async def list_targets(
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [t.model_dump() for t in tracker.list_targets(service=service)]


@router.get("/targets/{target_id}")
async def get_target(
    target_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    target = tracker.get_target(target_id)
    if target is None:
        raise HTTPException(404, f"Target '{target_id}' not found")
    return target.model_dump()


@router.delete("/targets/{target_id}")
async def delete_target(
    target_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    tracker = _get_tracker()
    if not tracker.delete_target(target_id):
        raise HTTPException(404, f"Target '{target_id}' not found")
    return {"status": "deleted"}


@router.post("/check")
async def check_violation(
    body: CheckViolationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    violation = tracker.check_violation(**body.model_dump())
    if violation is None:
        return {"violation": False}
    return {"violation": True, "detail": violation.model_dump()}


@router.get("/violations")
async def list_violations(
    service: str | None = None,
    severity: str | None = None,
    active_only: bool = False,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [
        v.model_dump()
        for v in tracker.list_violations(
            service=service, severity=severity, active_only=active_only
        )
    ]


@router.put("/violations/{violation_id}/resolve")
async def resolve_violation(
    violation_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    violation = tracker.resolve_violation(violation_id)
    if violation is None:
        raise HTTPException(404, f"Violation '{violation_id}' not found")
    return violation.model_dump()


@router.get("/report/{service}")
async def get_service_report(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_service_report(service).model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
