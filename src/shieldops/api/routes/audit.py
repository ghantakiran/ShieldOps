"""Audit log API routes."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/audit-logs", tags=["Audit"])

_repository: Any | None = None


def set_repository(repo: Any) -> None:
    """Set the repository instance for audit log route handlers."""
    global _repository
    _repository = repo


@router.get("")
async def list_audit_logs(
    request: Request,
    environment: str | None = Query(None),
    agent_type: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """List audit log entries (admin only). Paginated, filterable."""
    repo = _repository or getattr(request.app.state, "repository", None)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DB unavailable",
        )

    entries = await repo.list_audit_logs(environment=environment, limit=limit, offset=offset)

    # Client-side filtering for agent_type and action
    # (repository only supports environment filter)
    if agent_type:
        entries = [e for e in entries if e.get("agent_type") == agent_type]
    if action:
        entries = [e for e in entries if e.get("action") == action]

    return {
        "items": entries,
        "total": len(entries),
        "limit": limit,
        "offset": offset,
    }
