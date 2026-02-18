"""Playbook API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse

if TYPE_CHECKING:
    from shieldops.playbooks.loader import PlaybookLoader

router = APIRouter()

_loader: PlaybookLoader | None = None


def set_loader(loader: PlaybookLoader | None) -> None:
    """Set the playbook loader instance."""
    global _loader
    _loader = loader


@router.get("/playbooks")
async def list_playbooks(_user: UserResponse = Depends(get_current_user)) -> dict[str, Any]:
    """List all loaded remediation playbooks."""
    if _loader is None:
        return {"playbooks": [], "total": 0}

    playbooks = [
        {
            "name": pb.name,
            "version": pb.version,
            "description": pb.description,
            "trigger": pb.trigger.model_dump(),
            "decision_tree_count": len(pb.decision_tree),
        }
        for pb in _loader.all()
    ]
    return {"playbooks": playbooks, "total": len(playbooks)}


@router.get("/playbooks/{name}")
async def get_playbook(
    name: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a single playbook by name."""
    if _loader is None:
        raise HTTPException(status_code=404, detail="Playbook loader not initialized")

    pb = _loader.get(name)
    if pb is None:
        raise HTTPException(status_code=404, detail=f"Playbook '{name}' not found")

    return pb.model_dump()
