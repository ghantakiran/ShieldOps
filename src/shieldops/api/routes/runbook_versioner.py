"""Runbook versioner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/runbook-versioner",
    tags=["Runbook Versioner"],
)

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(
            503,
            "Runbook versioner service unavailable",
        )
    return _manager


# -- Request models -------------------------------------------------


class CreateVersionRequest(BaseModel):
    runbook_id: str
    steps: list[str] = []
    category: str = "INCIDENT_RESPONSE"
    author: str = ""
    change_type: str = "STEP_ADDED"
    change_summary: str = ""


class DiffVersionsRequest(BaseModel):
    version_id_a: str
    version_id_b: str


class RollbackRequest(BaseModel):
    runbook_id: str
    version_id: str


# -- Routes ---------------------------------------------------------


@router.post("/versions")
async def create_version(
    body: CreateVersionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    v = mgr.create_version(**body.model_dump())
    return v.model_dump()


@router.get("/versions")
async def list_versions(
    runbook_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [
        v.model_dump()
        for v in mgr.list_versions(
            runbook_id=runbook_id,
            status=status,
            limit=limit,
        )
    ]


@router.get("/versions/{version_id}")
async def get_version(
    version_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    v = mgr.get_version(version_id)
    if v is None:
        raise HTTPException(
            404,
            f"Version '{version_id}' not found",
        )
    return v.model_dump()


@router.post("/diff")
async def diff_versions(
    body: DiffVersionsRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    diff = mgr.diff_versions(**body.model_dump())
    if diff is None:
        raise HTTPException(404, "One or both versions not found")
    return diff.model_dump()


@router.post("/versions/{version_id}/approve")
async def approve_version(
    version_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    v = mgr.approve_version(version_id)
    if v is None:
        raise HTTPException(
            404,
            f"Version '{version_id}' not found",
        )
    return v.model_dump()


@router.post("/versions/{version_id}/publish")
async def publish_version(
    version_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    v = mgr.publish_version(version_id)
    if v is None:
        raise HTTPException(
            404,
            f"Version '{version_id}' not found",
        )
    return v.model_dump()


@router.post("/rollback")
async def rollback_to_version(
    body: RollbackRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    v = mgr.rollback_to_version(**body.model_dump())
    if v is None:
        raise HTTPException(404, "Runbook or version not found")
    return v.model_dump()


@router.get("/stale")
async def detect_stale_runbooks(
    max_age_days: int = 90,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return mgr.detect_stale_runbooks(max_age_days)


@router.get("/report")
async def generate_version_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.generate_version_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()
