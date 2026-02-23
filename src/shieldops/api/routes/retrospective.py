"""Incident retrospective API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/retrospectives", tags=["Retrospectives"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Retrospective service unavailable")
    return _manager


class CreateRetroRequest(BaseModel):
    incident_id: str
    title: str
    scheduled_at: float | None = None
    facilitator: str = ""
    participants: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


class CompleteRetroRequest(BaseModel):
    timeline: str = ""
    root_cause: str = ""
    impact_summary: str = ""
    lessons_learned: list[str] = Field(default_factory=list)


class AddActionItemRequest(BaseModel):
    description: str
    assignee: str = ""
    priority: str = "medium"
    due_date: float | None = None


@router.post("")
async def create_retrospective(
    body: CreateRetroRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    retro = mgr.create_retrospective(**body.model_dump())
    return retro.model_dump()


@router.get("")
async def list_retrospectives(
    status: str | None = None,
    incident_id: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [r.model_dump() for r in mgr.list_retrospectives(status=status, incident_id=incident_id)]


@router.get("/overdue-actions")
async def get_overdue_actions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return mgr.get_overdue_actions()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()


@router.get("/{retro_id}")
async def get_retrospective(
    retro_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    retro = mgr.get_retrospective(retro_id)
    if retro is None:
        raise HTTPException(404, f"Retrospective '{retro_id}' not found")
    return retro.model_dump()


@router.put("/{retro_id}/start")
async def start_retrospective(
    retro_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    retro = mgr.start_retrospective(retro_id)
    if retro is None:
        raise HTTPException(404, f"Retrospective '{retro_id}' not found")
    return retro.model_dump()


@router.put("/{retro_id}/complete")
async def complete_retrospective(
    retro_id: str,
    body: CompleteRetroRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    retro = mgr.complete_retrospective(retro_id=retro_id, **body.model_dump())
    if retro is None:
        raise HTTPException(404, f"Retrospective '{retro_id}' not found")
    return retro.model_dump()


@router.delete("/{retro_id}")
async def cancel_retrospective(
    retro_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    retro = mgr.cancel_retrospective(retro_id)
    if retro is None:
        raise HTTPException(404, f"Retrospective '{retro_id}' not found")
    return retro.model_dump()


@router.post("/{retro_id}/actions")
async def add_action_item(
    retro_id: str,
    body: AddActionItemRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    item = mgr.add_action_item(retro_id=retro_id, **body.model_dump())
    if item is None:
        raise HTTPException(404, f"Retrospective '{retro_id}' not found")
    return item.model_dump()


@router.put("/{retro_id}/actions/{item_id}/complete")
async def complete_action_item(
    retro_id: str,
    item_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    item = mgr.complete_action_item(retro_id=retro_id, item_id=item_id)
    if item is None:
        raise HTTPException(404, "Action item not found")
    return item.model_dump()
