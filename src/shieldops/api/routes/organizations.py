"""Organization management API routes (multi-tenant)."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role
from shieldops.api.auth.models import UserRole

logger = structlog.get_logger()
router = APIRouter(prefix="/organizations", tags=["Organizations"])

_repository: Any | None = None


def set_repository(repo: Any) -> None:
    """Set the repository instance for organization routes."""
    global _repository  # noqa: PLW0603
    _repository = repo


def _get_repo(request: Request) -> Any:
    repo = _repository or getattr(request.app.state, "repository", None)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return repo


# ── Request bodies ────────────────────────────────────────────


class CreateOrganizationBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    slug: str = Field(..., min_length=1, max_length=128)
    plan: str = Field("free", pattern=r"^(free|pro|enterprise)$")


class UpdateOrganizationBody(BaseModel):
    name: str | None = Field(None, max_length=256)
    plan: str | None = Field(None, pattern=r"^(free|pro|enterprise)$")
    is_active: bool | None = None
    rate_limit: int | None = Field(None, ge=0)


# ── Endpoints ─────────────────────────────────────────────────


@router.get("")
async def list_organizations(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _user: Any = Depends(require_role(UserRole.ADMIN)),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """List all organizations (admin only)."""
    repo = _get_repo(request)
    orgs = await repo.list_organizations(limit=limit, offset=offset)
    return {
        "items": orgs,
        "total": len(orgs),
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_organization(
    request: Request,
    body: CreateOrganizationBody,
    _user: Any = Depends(require_role(UserRole.ADMIN)),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Create a new organization (admin only)."""
    repo = _get_repo(request)
    try:
        org = await repo.create_organization(name=body.name, slug=body.slug, plan=body.plan)
    except Exception as exc:
        detail = str(exc)
        if "unique" in detail.lower() or "duplicate" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organization with this name or slug already exists",
            ) from exc
        raise  # pragma: no cover
    logger.info("organization_created", org_id=org["id"])
    return org  # type: ignore[no-any-return]


@router.get("/{org_id}")
async def get_organization(
    request: Request,
    org_id: str,
    _user: Any = Depends(require_role(UserRole.ADMIN)),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Get organization details."""
    repo = _get_repo(request)
    org: dict[str, Any] | None = await repo.get_organization(org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return org


@router.put("/{org_id}")
async def update_organization(
    request: Request,
    org_id: str,
    body: UpdateOrganizationBody,
    _user: Any = Depends(require_role(UserRole.ADMIN)),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Update an organization (admin only)."""
    repo = _get_repo(request)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    org: dict[str, Any] | None = await repo.update_organization(org_id, **updates)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    logger.info("organization_updated", org_id=org_id)
    return org
