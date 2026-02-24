"""Change failure tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/change-failure-tracker", tags=["Change Failure Tracker"])

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Change failure tracker service unavailable")
    return _tracker


class RecordDeploymentRequest(BaseModel):
    service_name: str
    team: str
    result: str = "SUCCESS"
    scope: str = "PATCH"
    description: str = ""
    recovery_time_minutes: float = 0.0


@router.post("/deployments")
async def record_deployment(
    body: RecordDeploymentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    deployment = tracker.record_deployment(**body.model_dump())
    return deployment.model_dump()


@router.get("/deployments")
async def list_deployments(
    service_name: str | None = None,
    team: str | None = None,
    result: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [
        d.model_dump()
        for d in tracker.list_deployments(
            service_name=service_name, team=team, result=result, limit=limit
        )
    ]


@router.get("/deployments/{dep_id}")
async def get_deployment(
    dep_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    deployment = tracker.get_deployment(dep_id)
    if deployment is None:
        raise HTTPException(404, f"Deployment '{dep_id}' not found")
    return deployment.model_dump()


@router.post("/failure-rate/{service_name}")
async def calculate_failure_rate(
    service_name: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    result = tracker.calculate_failure_rate(service_name)
    return result.model_dump()


@router.get("/failure-trend/{service_name}")
async def detect_failure_trend(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    result = tracker.detect_failure_trend(service_name)
    return result.model_dump()


@router.get("/reliability-ranking")
async def rank_services_by_reliability(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [r.model_dump() for r in tracker.rank_services_by_reliability()]


@router.get("/risky-changes")
async def identify_risky_change_types(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [r.model_dump() for r in tracker.identify_risky_change_types()]


@router.get("/recovery-time")
async def calculate_recovery_time(
    service_name: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    result = tracker.calculate_recovery_time(service_name=service_name)
    return result.model_dump()


@router.get("/report")
async def generate_failure_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.generate_failure_report()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
