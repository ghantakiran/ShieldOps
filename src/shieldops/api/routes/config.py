"""Configuration hot-reload API routes."""

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from shieldops.config.hot_reload import HotReloadManager

logger = structlog.get_logger()
router = APIRouter(prefix="/config", tags=["Configuration"])

_manager: HotReloadManager | None = None


def set_manager(manager: HotReloadManager) -> None:
    global _manager
    _manager = manager


def _get_manager() -> HotReloadManager:
    if _manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Hot reload manager not initialized",
        )
    return _manager


class ReloadRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    source: str = "api"


@router.get("")
async def get_runtime_config() -> dict[str, Any]:
    """Get current runtime configuration (secrets redacted)."""
    manager = _get_manager()
    config = manager.get_runtime_config(redact_secrets=True)
    return {
        "config": config,
        "reload_count": manager.reload_count,
        "last_reload": manager.last_reload.isoformat() if manager.last_reload else None,
    }


@router.post("/reload")
async def reload_config(request: ReloadRequest) -> dict[str, Any]:
    """Trigger a configuration reload."""
    manager = _get_manager()
    success = manager.reload(request.config, source=request.source)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Configuration validation failed",
        )
    return {
        "status": "reloaded",
        "reload_count": manager.reload_count,
    }


@router.get("/changes")
async def get_config_changes(
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Get recent configuration change history."""
    manager = _get_manager()
    changes = manager.get_change_history(limit=limit)
    return {
        "changes": changes,
        "total": len(changes),
    }
