"""Dependency SLA tracking API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/dependency-slas", tags=["Dependency SLAs"])

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Dependency SLA service unavailable")
    return _tracker


class CreateSLARequest(BaseModel):
    upstream_service: str
    downstream_service: str
    sla_type: str
    target_value: float
    warning_threshold: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluateSLARequest(BaseModel):
    sla_id: str
    measured_value: float
    details: str = ""


@router.post("/slas")
async def create_sla(
    body: CreateSLARequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    sla = tracker.create_sla(**body.model_dump())
    return sla.model_dump()


@router.get("/slas")
async def list_slas(
    upstream: str | None = None,
    downstream: str | None = None,
    status: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [
        s.model_dump()
        for s in tracker.list_slas(upstream=upstream, downstream=downstream, status=status)
    ]


@router.get("/slas/{sla_id}")
async def get_sla(
    sla_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    sla = tracker.get_sla(sla_id)
    if sla is None:
        raise HTTPException(404, f"SLA '{sla_id}' not found")
    return sla.model_dump()


@router.delete("/slas/{sla_id}")
async def delete_sla(
    sla_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    removed = tracker.delete_sla(sla_id)
    if not removed:
        raise HTTPException(404, f"SLA '{sla_id}' not found")
    return {"deleted": True, "sla_id": sla_id}


@router.post("/evaluations")
async def evaluate_sla(
    body: EvaluateSLARequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    evaluation = tracker.evaluate_sla(**body.model_dump())
    return evaluation.model_dump()


@router.get("/evaluations")
async def get_evaluations(
    sla_id: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [e.model_dump() for e in tracker.get_evaluations(sla_id=sla_id, limit=limit)]


@router.get("/cascade-risks")
async def detect_cascade_risks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [r.model_dump() for r in tracker.detect_cascade_risks()]


@router.get("/services/{service}/report")
async def get_service_report(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    report = tracker.get_service_report(service)
    # Serialize any Pydantic models in the report
    result: dict[str, Any] = {}
    for key, value in report.items():
        if isinstance(value, list):
            result[key] = [
                item.model_dump() if hasattr(item, "model_dump") else item for item in value
            ]
        else:
            result[key] = value
    return result


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
