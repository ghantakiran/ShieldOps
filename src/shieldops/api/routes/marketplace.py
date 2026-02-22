"""Marketplace API endpoints — browse and deploy agent templates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

if TYPE_CHECKING:
    from shieldops.playbooks.template_loader import TemplateLoader

logger = structlog.get_logger()

router = APIRouter()

_template_loader: TemplateLoader | None = None


def set_template_loader(loader: TemplateLoader | None) -> None:
    """Set the template loader instance (called during app startup)."""
    global _template_loader
    _template_loader = loader


# ── Request / Response Models ─────────────────────────────────────


class TemplateParameterResponse(BaseModel):
    """A configurable parameter exposed by a template."""

    name: str
    type: str = "string"
    required: bool = True
    default: Any = None
    description: str = ""


class TemplateStepResponse(BaseModel):
    """A single step in a template's execution plan."""

    name: str
    action: str
    config: dict[str, Any] = Field(default_factory=dict)


class AgentTemplateResponse(BaseModel):
    """Full representation of an agent template."""

    id: str
    name: str
    description: str = ""
    category: str
    cloud_providers: list[str] = Field(default_factory=list)
    agent_type: str
    risk_level: str
    tags: list[str] = Field(default_factory=list)
    estimated_setup_minutes: int = 5
    featured: bool = False
    parameters: list[TemplateParameterResponse] = Field(default_factory=list)
    steps: list[TemplateStepResponse] = Field(default_factory=list)


class TemplateDeployRequest(BaseModel):
    """Request body for deploying a template."""

    template_id: str
    org_id: str = "default"
    environment: str = "production"
    parameters: dict[str, Any] = Field(default_factory=dict)


class TemplateDeployResponse(BaseModel):
    """Response after a successful template deployment."""

    deployment_id: str
    template_id: str
    template_name: str
    org_id: str
    environment: str
    agent_type: str
    category: str
    risk_level: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "deployed"


class CategoryCountResponse(BaseModel):
    """A category with its template count."""

    category: str
    count: int


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("/marketplace/templates")
async def list_templates(
    category: str | None = Query(None, description="Filter by category"),
    cloud: str | None = Query(None, description="Filter by cloud provider"),
    tags: str | None = Query(None, description="Comma-separated tag filter"),
    q: str | None = Query(None, description="Free-text search query"),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all agent templates with optional filters."""
    if _template_loader is None:
        return {"templates": [], "total": 0}

    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    templates = _template_loader.search(
        category=category,
        cloud=cloud,
        tags=tag_list,
        query=q,
    )

    return {
        "templates": [AgentTemplateResponse(**t.model_dump()).model_dump() for t in templates],
        "total": len(templates),
    }


@router.get("/marketplace/templates/{template_id}")
async def get_template(
    template_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> AgentTemplateResponse:
    """Get a single template by ID."""
    if _template_loader is None:
        raise HTTPException(
            status_code=503,
            detail="Template loader not initialized",
        )

    template = _template_loader.get_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_id}' not found",
        )

    return AgentTemplateResponse(**template.model_dump())


@router.post("/marketplace/deploy")
async def deploy_template(
    body: TemplateDeployRequest,
    _user: UserResponse = Depends(get_current_user),
) -> TemplateDeployResponse:
    """Deploy an agent template — creates agent config and playbook from template."""
    if _template_loader is None:
        raise HTTPException(
            status_code=503,
            detail="Template loader not initialized",
        )

    try:
        result = _template_loader.deploy(
            template_id=body.template_id,
            org_id=body.org_id,
            environment=body.environment,
            params=body.parameters,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info(
        "template_deployed",
        template_id=body.template_id,
        org_id=body.org_id,
        environment=body.environment,
        user=_user.id,
    )

    return TemplateDeployResponse(**result)


@router.get("/marketplace/categories")
async def list_categories(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List available categories with template counts."""
    if _template_loader is None:
        return {"categories": [], "total": 0}

    counts = _template_loader.categories()
    categories = [
        CategoryCountResponse(category=cat, count=cnt).model_dump()
        for cat, cnt in sorted(counts.items())
    ]

    return {"categories": categories, "total": len(categories)}


@router.get("/marketplace/featured")
async def list_featured(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Return curated featured templates."""
    if _template_loader is None:
        return {"templates": [], "total": 0}

    featured = _template_loader.featured()

    return {
        "templates": [AgentTemplateResponse(**t.model_dump()).model_dump() for t in featured],
        "total": len(featured),
    }
