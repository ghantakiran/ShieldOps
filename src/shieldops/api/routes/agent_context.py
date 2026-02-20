"""Agent context API routes — persistent cross-incident memory."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from shieldops.agents.context_store import AgentContextStore
from shieldops.api.auth.dependencies import (
    get_current_user,
    require_role,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/agent-context", tags=["Agent Context"])

_store: AgentContextStore | None = None


def set_store(store: AgentContextStore) -> None:
    """Wire the context store at startup."""
    global _store
    _store = store


def _get_store() -> AgentContextStore:
    if _store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent context store unavailable",
        )
    return _store


# ── Request / Response models ──────────────────────────────────


class ContextSetBody(BaseModel):
    """Payload for setting a context value."""

    value: dict[str, Any] = Field(..., description="Context value to store")
    ttl_hours: int | None = Field(
        None,
        description="Optional TTL in hours; None means no expiry",
    )


# ── Routes ─────────────────────────────────────────────────────


@router.get("")
async def list_context(
    agent_type: str = Query(..., description="Agent type to filter by"),
    key_pattern: str | None = Query(None, description="Optional key substring filter"),
    _user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """List context entries for a given agent type."""
    store = _get_store()
    entries = await store.search(agent_type, key_pattern)
    return {
        "items": entries,
        "total": len(entries),
        "agent_type": agent_type,
    }


@router.get("/{agent_type}/{key}")
async def get_context(
    agent_type: str,
    key: str,
    _user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific context entry by agent type and key."""
    store = _get_store()
    value = await store.get(agent_type, key)
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(f"Context not found: {agent_type}/{key}"),
        )
    return {
        "agent_type": agent_type,
        "key": key,
        "value": value,
    }


@router.put("/{agent_type}/{key}")
async def set_context(
    agent_type: str,
    key: str,
    body: ContextSetBody,
    _user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """Set or update a context entry."""
    store = _get_store()
    await store.set(agent_type, key, body.value, body.ttl_hours)
    logger.info(
        "context_set_via_api",
        agent_type=agent_type,
        key=key,
        ttl_hours=body.ttl_hours,
    )
    return {
        "agent_type": agent_type,
        "key": key,
        "value": body.value,
        "ttl_hours": body.ttl_hours,
    }


@router.delete("/{agent_type}/{key}")
async def delete_context(
    agent_type: str,
    key: str,
    _user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete a context entry."""
    store = _get_store()
    deleted = await store.delete(agent_type, key)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(f"Context not found: {agent_type}/{key}"),
        )
    return {"deleted": True, "agent_type": agent_type, "key": key}


@router.post("/cleanup")
async def cleanup_expired(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Trigger cleanup of all expired context entries (admin only)."""
    store = _get_store()
    count = await store.cleanup_expired()
    logger.info("context_cleanup_via_api", deleted_count=count)
    return {"deleted_count": count}
