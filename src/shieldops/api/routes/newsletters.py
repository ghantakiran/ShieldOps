"""Newsletter API endpoints."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = structlog.get_logger()
router = APIRouter(prefix="/newsletters")

_service: Any | None = None
_repository: Any | None = None


def set_service(service: Any) -> None:
    """Set the newsletter service instance for route handlers."""
    global _service
    _service = service


def set_repository(repository: Any) -> None:
    """Set the repository instance for route handlers."""
    global _repository
    _repository = repository


class SendNewsletterRequest(BaseModel):
    """Request body for triggering a manual newsletter send."""

    frequency: str = "weekly"
    recipients: list[str] | None = None
    team_id: str | None = None


class NewsletterConfigUpdate(BaseModel):
    """Request body for updating newsletter configuration."""

    frequency: str = "weekly"
    include_new_vulns: bool = True
    include_sla_breaches: bool = True
    include_remediation_progress: bool = True
    include_posture_trend: bool = True
    include_top_risks: bool = True
    include_industry_alerts: bool = True
    max_vulnerabilities: int = 50
    team_id: str | None = None


@router.post("/send")
async def send_newsletter(request: SendNewsletterRequest) -> dict[str, Any]:
    """Trigger manual newsletter send."""
    if not _service:
        raise HTTPException(status_code=503, detail="Newsletter service not configured")

    digest = await _service.preview(frequency=request.frequency)
    result = await _service.send_digest(
        digest=digest,
        recipients=request.recipients,
        team_id=request.team_id,
    )
    return result


@router.get("/preview")
async def preview_newsletter(
    frequency: str = Query(default="weekly", pattern="^(daily|weekly)$"),
    team_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """Preview next newsletter without sending."""
    if not _service:
        raise HTTPException(status_code=503, detail="Newsletter service not configured")

    from shieldops.vulnerability.newsletter import NewsletterConfig

    config = NewsletterConfig(frequency=frequency, team_id=team_id)
    return await _service.preview(frequency=frequency, config=config)


@router.put("/config")
async def update_config(config: NewsletterConfigUpdate) -> dict[str, Any]:
    """Update newsletter configuration."""
    # In production, persist to DB. For now, return acknowledgement.
    return {"status": "updated", "config": config.model_dump()}


@router.get("/history")
async def list_history(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """List past newsletters."""
    if not _repository:
        return []
    try:
        return await _repository.list_newsletter_history(limit=limit)
    except Exception:
        return []
