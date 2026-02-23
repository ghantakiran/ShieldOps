"""Environment promotion workflow API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role
from shieldops.config.environment_promotion import PromotionStatus

logger = structlog.get_logger()
router = APIRouter(prefix="/environments", tags=["Environment Promotion"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Promotion service unavailable")
    return _manager


class PreviewRequest(BaseModel):
    source_env: str
    target_env: str


class PromoteRequest(BaseModel):
    source_env: str
    target_env: str
    requested_by: str = ""
    resource_types: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    reviewed_by: str = ""
    comment: str = ""


@router.post("/promote/preview")
async def preview_promotion(
    body: PreviewRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    diffs = mgr.preview(body.source_env, body.target_env)
    return [d.model_dump() for d in diffs]


@router.post("/promote")
async def create_promotion(
    body: PromoteRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    try:
        req = mgr.create_request(
            body.source_env,
            body.target_env,
            body.requested_by,
            body.resource_types or None,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return req.model_dump()


@router.post("/promote/{request_id}/approve")
async def approve_promotion(
    request_id: str,
    body: ReviewRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    req = mgr.approve(request_id, body.reviewed_by, body.comment)
    if req is None:
        raise HTTPException(404, "Request not found or not pending")
    return req.model_dump()


@router.post("/promote/{request_id}/reject")
async def reject_promotion(
    request_id: str,
    body: ReviewRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    req = mgr.reject(request_id, body.reviewed_by, body.comment)
    if req is None:
        raise HTTPException(404, "Request not found or not pending")
    return req.model_dump()


@router.post("/promote/{request_id}/apply")
async def apply_promotion(
    request_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    req = mgr.apply(request_id)
    if req is None:
        raise HTTPException(404, "Request not found or not approved")
    return req.model_dump()


@router.post("/promote/{request_id}/rollback")
async def rollback_promotion(
    request_id: str,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    req = mgr.rollback(request_id)
    if req is None:
        raise HTTPException(404, "Request not found or not applied")
    return req.model_dump()


@router.get("/promote/{request_id}")
async def get_promotion(
    request_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    req = mgr.get_request(request_id)
    if req is None:
        raise HTTPException(404, "Request not found")
    return req.model_dump()


@router.get("/promote")
async def list_promotions(
    status: PromotionStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [r.model_dump() for r in mgr.list_requests(status, limit)]


@router.get("/{env}/snapshot")
async def get_environment_snapshot(
    env: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_snapshot(env)
