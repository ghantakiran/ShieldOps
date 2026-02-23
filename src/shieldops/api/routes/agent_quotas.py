"""Agent resource quota API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/agents/quotas", tags=["Agent Quotas"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Quota service unavailable")
    return _manager


class UpdateQuotaRequest(BaseModel):
    max_concurrent: int | None = None
    max_per_hour: int | None = None
    max_per_day: int | None = None
    priority: int | None = None


@router.get("")
async def list_agent_quotas(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [q.model_dump() for q in mgr.list_quotas()]


@router.put("/{agent_type}")
async def update_agent_quota(
    agent_type: str,
    body: UpdateQuotaRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    from shieldops.agents.resource_quotas import QuotaConfig

    mgr = _get_manager()
    existing = mgr.get_quota(agent_type)
    if existing is None:
        existing = QuotaConfig(agent_type=agent_type)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    for k, v in updates.items():
        setattr(existing, k, v)
    mgr.set_quota(existing)
    return existing.model_dump()


@router.get("/{agent_type}/usage")
async def get_agent_quota_usage(
    agent_type: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_usage(agent_type).model_dump()


@router.get("/stats/overview")
async def get_quota_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()


@router.post("/reset")
async def reset_quota_counters(
    agent_type: str | None = None,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, str]:
    mgr = _get_manager()
    mgr.reset(agent_type)
    return {"reset": agent_type or "all"}
