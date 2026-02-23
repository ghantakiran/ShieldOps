"""Orphaned resource detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/orphan-detector",
    tags=["Orphan Detector"],
)

_detector: Any = None


def set_detector(detector: Any) -> None:
    global _detector
    _detector = detector


def _get_detector() -> Any:
    if _detector is None:
        raise HTTPException(503, "Orphan detector service unavailable")
    return _detector


class ReportOrphanRequest(BaseModel):
    resource_id: str
    resource_type: str = ""
    category: str = "unattached_volume"
    risk: str = "low"
    provider: str = ""
    region: str = ""
    monthly_cost: float = 0.0


class ExecuteCleanupRequest(BaseModel):
    success: bool = True
    notes: str = ""


@router.post("/orphans")
async def report_orphan(
    body: ReportOrphanRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    orphan = det.report_orphan(
        resource_id=body.resource_id,
        resource_type=body.resource_type,
        category=body.category,
        risk=body.risk,
        provider=body.provider,
        region=body.region,
        monthly_cost=body.monthly_cost,
    )
    return orphan.model_dump()


@router.get("/orphans")
async def list_orphans(
    category: str | None = None,
    action: str | None = None,
    provider: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    det = _get_detector()
    orphans = det.list_orphans(category=category, action=action, provider=provider)
    return [o.model_dump() for o in orphans[-limit:]]


@router.get("/orphans/{orphan_id}")
async def get_orphan(
    orphan_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    orphan = det.get_orphan(orphan_id)
    if orphan is None:
        raise HTTPException(404, f"Orphan '{orphan_id}' not found")
    return orphan.model_dump()


@router.put("/orphans/{orphan_id}/flag")
async def flag_for_cleanup(
    orphan_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    orphan = det.flag_for_cleanup(orphan_id)
    if orphan is None:
        raise HTTPException(404, f"Orphan '{orphan_id}' not found")
    return orphan.model_dump()


@router.put("/orphans/{orphan_id}/exempt")
async def exempt_resource(
    orphan_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    orphan = det.exempt_resource(orphan_id)
    if orphan is None:
        raise HTTPException(404, f"Orphan '{orphan_id}' not found")
    return orphan.model_dump()


@router.post("/cleanup")
async def schedule_cleanup(
    orphan_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    job = det.schedule_cleanup(orphan_id)
    if job is None:
        raise HTTPException(404, f"Orphan '{orphan_id}' not found")
    return job.model_dump()


@router.put("/cleanup/{job_id}")
async def execute_cleanup(
    job_id: str,
    body: ExecuteCleanupRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    job = det.execute_cleanup(job_id, success=body.success, notes=body.notes)
    if job is None:
        raise HTTPException(404, f"Cleanup job '{job_id}' not found")
    return job.model_dump()


@router.get("/waste")
async def get_monthly_waste(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    return det.get_monthly_waste()


@router.get("/summary")
async def get_summary(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    return det.get_summary().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    return det.get_stats()
