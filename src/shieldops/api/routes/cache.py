"""Cache management API endpoints.

Provides admin-only routes for inspecting cache statistics,
invalidating cached data, and verifying Redis health.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/cache", tags=["Cache"])

_cache: Any = None


def set_cache(cache: Any) -> None:
    """Wire the RedisCache instance into this route module."""
    global _cache
    _cache = cache


def _get_cache() -> Any:
    if _cache is None:
        raise HTTPException(503, "Cache service unavailable")
    return _cache


class InvalidateRequest(BaseModel):
    """Request body for cache invalidation."""

    namespace: str | None = None


@router.get("/stats")
async def cache_stats(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Return cache hit/miss ratio and key count (admin only)."""
    cache = _get_cache()
    stats: dict[str, Any] = await cache.get_stats()
    return stats


@router.post("/invalidate")
async def cache_invalidate(
    body: InvalidateRequest | None = None,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Clear all cached data or a specific namespace (admin only)."""
    cache = _get_cache()
    if body and body.namespace:
        deleted = await cache.invalidate_pattern(f"{body.namespace}:*")
    else:
        deleted = await cache.flush_all()
    logger.info(
        "cache_invalidated_via_api",
        namespace=body.namespace if body else None,
        deleted=deleted,
    )
    return {"invalidated": True, "keys_deleted": deleted}


@router.get("/health")
async def cache_health() -> dict[str, Any]:
    """Check Redis connectivity (no auth required)."""
    cache = _get_cache()
    result: dict[str, Any] = await cache.health_check()
    return result


# ── Multi-Level Cache ────────────────────────────────────────────

_multilevel_cache: Any = None


def set_multilevel_cache(cache: Any) -> None:
    """Wire the MultiLevelCache instance into this route module."""
    global _multilevel_cache
    _multilevel_cache = cache


@router.get("/stats/multilevel")
async def multilevel_cache_stats(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Return L1+L2 cache statistics (admin only)."""
    if _multilevel_cache is None:
        raise HTTPException(503, "Multi-level cache not configured")
    return _multilevel_cache.get_stats().model_dump()  # type: ignore[no-any-return]


class WarmupRequest(BaseModel):
    """Request body for cache warmup."""

    keys: list[dict[str, str]]


@router.post("/warmup")
async def cache_warmup(
    body: WarmupRequest,
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Pre-populate L1 from L2 for given keys (admin only)."""
    if _multilevel_cache is None:
        raise HTTPException(503, "Multi-level cache not configured")
    warmed = await _multilevel_cache.warmup(body.keys)
    return {"warmed": warmed, "requested": len(body.keys)}
