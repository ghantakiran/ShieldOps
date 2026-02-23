"""Release management API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/release-manager",
    tags=["Release Manager"],
)

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Release manager service unavailable")
    return _tracker


class CreateReleaseRequest(BaseModel):
    version: str
    service: str
    release_type: str = "minor"
    description: str = ""
    author: str = ""
    changes: list[str] = []


class ApprovalRequest(BaseModel):
    approver: str
    comment: str = ""


@router.post("/releases")
async def create_release(
    body: CreateReleaseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    release = tracker.create_release(
        version=body.version,
        service=body.service,
        release_type=body.release_type,
        description=body.description,
        author=body.author,
        changes=body.changes,
    )
    return release.model_dump()


@router.get("/releases")
async def list_releases(
    service: str | None = None,
    status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    releases = tracker.list_releases(service=service, status=status)
    return [r.model_dump() for r in releases[-limit:]]


@router.get("/releases/{release_id}")
async def get_release(
    release_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    release = tracker.get_release(release_id)
    if release is None:
        raise HTTPException(404, f"Release '{release_id}' not found")
    return release.model_dump()


@router.put("/releases/{release_id}/submit")
async def submit_for_approval(
    release_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    release = tracker.submit_for_approval(release_id)
    if release is None:
        raise HTTPException(404, f"Release '{release_id}' not found")
    return release.model_dump()


@router.post("/releases/{release_id}/approve")
async def approve_release(
    release_id: str,
    body: ApprovalRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    approval = tracker.approve_release(
        release_id,
        approver=body.approver,
        comment=body.comment,
    )
    if approval is None:
        raise HTTPException(404, f"Release '{release_id}' not found")
    return approval.model_dump()


@router.post("/releases/{release_id}/reject")
async def reject_release(
    release_id: str,
    body: ApprovalRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    approval = tracker.reject_release(
        release_id,
        approver=body.approver,
        comment=body.comment,
    )
    if approval is None:
        raise HTTPException(404, f"Release '{release_id}' not found")
    return approval.model_dump()


@router.put("/releases/{release_id}/release")
async def mark_released(
    release_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    release = tracker.mark_released(release_id)
    if release is None:
        raise HTTPException(404, f"Release '{release_id}' not found or not approved")
    return release.model_dump()


@router.put("/releases/{release_id}/rollback")
async def rollback_release(
    release_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    release = tracker.rollback_release(release_id)
    if release is None:
        raise HTTPException(404, f"Release '{release_id}' not found")
    return release.model_dump()


@router.get("/releases/{release_id}/notes")
async def get_release_notes(
    release_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    notes = tracker.generate_release_notes(release_id)
    if not notes:
        raise HTTPException(404, f"Release '{release_id}' not found")
    return notes


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
