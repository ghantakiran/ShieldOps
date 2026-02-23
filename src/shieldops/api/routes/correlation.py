"""Request correlation API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/correlation", tags=["Correlation"])

_correlator: Any = None


def set_correlator(correlator: Any) -> None:
    global _correlator
    _correlator = correlator


def _get_correlator() -> Any:
    if _correlator is None:
        raise HTTPException(503, "Correlation service unavailable")
    return _correlator


@router.get("/traces/{request_id}")
async def get_trace(
    request_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    corr = _get_correlator()
    trace = corr.get_trace(request_id)
    if trace is None:
        raise HTTPException(404, f"Trace '{request_id}' not found")
    return trace.model_dump()


@router.get("/traces")
async def list_traces(
    entry_point: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    corr = _get_correlator()
    return [t.model_dump() for t in corr.search_traces(entry_point=entry_point, limit=limit)]


@router.get("/traces/slow")
async def get_slow_traces(
    threshold_ms: float = 1000.0,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    corr = _get_correlator()
    return [t.model_dump() for t in corr.get_slow_traces(threshold_ms, limit)]


@router.get("/stats")
async def get_correlation_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    corr = _get_correlator()
    return corr.get_stats()


@router.post("/cleanup")
async def cleanup_traces(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, int]:
    corr = _get_correlator()
    removed = corr.cleanup_old_traces()
    return {"removed": removed}
