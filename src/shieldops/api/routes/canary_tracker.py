"""Canary deployment tracking API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/canary-deployments", tags=["Canary Deployments"])

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Canary deployment service unavailable")
    return _tracker


class CreateDeploymentRequest(BaseModel):
    service: str
    version: str
    baseline_version: str = ""
    target_traffic_pct: float = 100.0
    steps: list[float] = Field(default_factory=lambda: [5.0, 25.0, 50.0, 75.0, 100.0])
    success_threshold: float = 0.95
    error_rate_limit: float = 0.05
    owner: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordMetricRequest(BaseModel):
    deployment_id: str
    metric_name: str
    baseline_value: float
    canary_value: float


@router.post("/deployments")
async def create_deployment(
    body: CreateDeploymentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    deployment = tracker.create_deployment(**body.model_dump())
    return deployment.model_dump()


@router.get("/deployments")
async def list_deployments(
    service: str | None = None,
    phase: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [d.model_dump() for d in tracker.list_deployments(service=service, phase=phase)]


@router.get("/deployments/{deployment_id}")
async def get_deployment(
    deployment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    deployment = tracker.get_deployment(deployment_id)
    if deployment is None:
        raise HTTPException(404, f"Deployment '{deployment_id}' not found")
    return deployment.model_dump()


@router.put("/deployments/{deployment_id}/start")
async def start_canary(
    deployment_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    deployment = tracker.start_canary(deployment_id)
    if deployment is None:
        raise HTTPException(404, f"Deployment '{deployment_id}' not found")
    return deployment.model_dump()


@router.put("/deployments/{deployment_id}/advance")
async def advance_canary(
    deployment_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    deployment = tracker.advance_canary(deployment_id)
    if deployment is None:
        raise HTTPException(404, f"Deployment '{deployment_id}' not found")
    return deployment.model_dump()


@router.put("/deployments/{deployment_id}/promote")
async def promote_canary(
    deployment_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    deployment = tracker.promote_canary(deployment_id)
    if deployment is None:
        raise HTTPException(404, f"Deployment '{deployment_id}' not found")
    return deployment.model_dump()


@router.put("/deployments/{deployment_id}/rollback")
async def rollback_canary(
    deployment_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    deployment = tracker.rollback_canary(deployment_id)
    if deployment is None:
        raise HTTPException(404, f"Deployment '{deployment_id}' not found")
    return deployment.model_dump()


@router.put("/deployments/{deployment_id}/pause")
async def pause_canary(
    deployment_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    deployment = tracker.pause_canary(deployment_id)
    if deployment is None:
        raise HTTPException(404, f"Deployment '{deployment_id}' not found")
    return deployment.model_dump()


@router.post("/metrics")
async def record_metric(
    body: RecordMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    metric = tracker.record_metric(**body.model_dump())
    return metric.model_dump()


@router.get("/metrics/{deployment_id}")
async def get_metrics(
    deployment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [m.model_dump() for m in tracker.get_metrics(deployment_id)]


@router.get("/deployments/{deployment_id}/should-rollback")
async def should_rollback(
    deployment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    result = tracker.should_rollback(deployment_id)
    return {"deployment_id": deployment_id, "should_rollback": result}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
