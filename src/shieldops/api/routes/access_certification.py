"""Access certification API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/access-certification",
    tags=["Access Certification"],
)

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Access certification service unavailable")
    return _manager


class RegisterGrantRequest(BaseModel):
    user: str
    resource: str
    scope: str = "read_only"
    expires_at: float | None = None


class CreateCampaignRequest(BaseModel):
    name: str
    cycle: str = "quarterly"
    scope_filter: str = ""


class CertifyRequest(BaseModel):
    reviewer: str = ""
    campaign_id: str = ""
    comment: str = ""


class RevokeRequest(BaseModel):
    reviewer: str = ""
    campaign_id: str = ""
    comment: str = ""


@router.post("/grants")
async def register_grant(
    body: RegisterGrantRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    grant = mgr.register_grant(
        user=body.user,
        resource=body.resource,
        scope=body.scope,
        expires_at=body.expires_at,
    )
    return grant.model_dump()


@router.get("/grants")
async def list_grants(
    user: str | None = None,
    resource: str | None = None,
    status: str | None = None,
    scope: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    grants = mgr.list_grants(user=user, resource=resource, status=status, scope=scope)
    return [g.model_dump() for g in grants[-limit:]]


@router.get("/grants/{grant_id}")
async def get_grant(
    grant_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    grant = mgr.get_grant(grant_id)
    if grant is None:
        raise HTTPException(404, f"Grant '{grant_id}' not found")
    return grant.model_dump()


@router.post("/campaigns")
async def create_campaign(
    body: CreateCampaignRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    campaign = mgr.create_campaign(
        name=body.name,
        cycle=body.cycle,
        scope_filter=body.scope_filter,
    )
    return campaign.model_dump()


@router.get("/campaigns")
async def list_campaigns(
    cycle: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    campaigns = mgr.list_campaigns(cycle=cycle)
    return [c.model_dump() for c in campaigns]


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    campaign = mgr.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(404, f"Campaign '{campaign_id}' not found")
    return campaign.model_dump()


@router.post("/grants/{grant_id}/certify")
async def certify_grant(
    grant_id: str,
    body: CertifyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    decision = mgr.certify_grant(
        grant_id,
        reviewer=body.reviewer,
        campaign_id=body.campaign_id,
        comment=body.comment,
    )
    if decision is None:
        raise HTTPException(404, f"Grant '{grant_id}' not found")
    return decision.model_dump()


@router.post("/grants/{grant_id}/revoke")
async def revoke_grant(
    grant_id: str,
    body: RevokeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    decision = mgr.revoke_grant(
        grant_id,
        reviewer=body.reviewer,
        campaign_id=body.campaign_id,
        comment=body.comment,
    )
    if decision is None:
        raise HTTPException(404, f"Grant '{grant_id}' not found")
    return decision.model_dump()


@router.get("/expired")
async def get_expired_grants(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    expired = mgr.get_expired_grants()
    return [g.model_dump() for g in expired]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()
