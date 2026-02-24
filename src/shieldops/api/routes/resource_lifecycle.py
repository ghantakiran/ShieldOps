"""Resource lifecycle tracking API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/resource-lifecycle", tags=["Resource Lifecycle"])

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Resource lifecycle service unavailable")
    return _tracker


class RegisterResourceRequest(BaseModel):
    resource_name: str
    category: str = "COMPUTE"
    owner: str = ""
    environment: str = "production"
    monthly_cost: float = 0.0


class TransitionRequest(BaseModel):
    to_phase: str
    reason: str = "planned"


@router.post("/resources")
async def register_resource(
    body: RegisterResourceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    resource = tracker.register_resource(**body.model_dump())
    return resource.model_dump()


@router.get("/resources")
async def list_resources(
    category: str | None = None,
    phase: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [
        r.model_dump() for r in tracker.list_resources(category=category, phase=phase, limit=limit)
    ]


@router.get("/resources/{resource_id}")
async def get_resource(
    resource_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    resource = tracker.get_resource(resource_id)
    if resource is None:
        raise HTTPException(404, f"Resource '{resource_id}' not found")
    return resource.model_dump()


@router.post("/resources/{resource_id}/transition")
async def transition_phase(
    resource_id: str,
    body: TransitionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    resource = tracker.transition_phase(resource_id=resource_id, **body.model_dump())
    if resource is None:
        raise HTTPException(404, f"Resource '{resource_id}' not found")
    return resource.model_dump()


@router.get("/transitions")
async def list_transitions(
    resource_id: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [t.model_dump() for t in tracker.list_transitions(resource_id=resource_id, limit=limit)]


@router.get("/stale")
async def detect_stale_resources(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [r.model_dump() for r in tracker.detect_stale_resources()]


@router.get("/decommission-candidates")
async def get_decommission_candidates(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [r.model_dump() for r in tracker.get_decommission_candidates()]


@router.get("/age-distribution")
async def compute_age_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.compute_age_distribution()


@router.get("/summary")
async def generate_summary(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.generate_summary()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
