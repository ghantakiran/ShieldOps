"""API routes for git-backed playbook synchronization."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

logger = structlog.get_logger()
router = APIRouter()

_sync: Any | None = None


def set_git_sync(sync: Any) -> None:
    global _sync
    _sync = sync


class SyncRequest(BaseModel):
    force: bool = False


class RollbackRequest(BaseModel):
    commit_sha: str


class ConfigureRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    playbook_dir: str = "playbooks"
    auto_sync: bool = False


@router.get("/playbooks/git-status")
async def git_status(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current git sync status."""
    if not _sync:
        return {
            "configured": False,
            "message": "Git sync not configured",
        }
    status: dict[str, Any] = await _sync.get_status()
    status["configured"] = True
    return status


@router.post("/playbooks/sync")
async def sync_playbooks(
    request: SyncRequest | None = None,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Sync playbooks from remote git repository."""
    if not _sync:
        raise HTTPException(status_code=503, detail="Git sync not configured")

    try:
        if request and request.force:
            result = await _sync.clone()
        else:
            result = await _sync.pull()
        return {"sync_result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}") from e


@router.get("/playbooks/git-diff")
async def diff_preview(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Preview changes between local and remote."""
    if not _sync:
        return {"changes": [], "total": 0}
    changes = await _sync.diff_preview()
    return {"changes": changes, "total": len(changes)}


@router.get("/playbooks/git-history")
async def version_history(
    limit: int = Query(20, ge=1, le=100),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get commit history for playbook files."""
    if not _sync:
        return {"commits": [], "total": 0}
    commits = await _sync.get_version_history(limit=limit)
    return {"commits": commits, "total": len(commits)}


@router.post("/playbooks/rollback")
async def rollback_playbooks(
    request: RollbackRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Rollback playbooks to a specific commit."""
    if not _sync:
        raise HTTPException(status_code=503, detail="Git sync not configured")
    try:
        result = await _sync.rollback(request.commit_sha)
        return {"rollback_result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {e}") from e


@router.get("/playbooks/git-files")
async def list_git_files(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List playbook files in synced repository."""
    if not _sync:
        return {"files": [], "total": 0}
    files = await _sync.list_playbook_files()
    return {"files": files, "total": len(files)}


@router.get("/playbooks/sync-history")
async def sync_history(
    limit: int = Query(20, ge=1, le=100),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get history of sync operations."""
    if not _sync:
        return {"history": [], "total": 0}
    history = _sync.get_sync_history(limit=limit)
    return {"history": history, "total": len(history)}
