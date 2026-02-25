"""Post-incident action tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.action_tracker import (
    ActionCategory,
    ActionPriority,
    ActionStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/post-incident-actions",
    tags=["Post-Incident Actions"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Post-incident action service unavailable")
    return _engine


class RecordActionRequest(BaseModel):
    incident_id: str
    title: str
    assignee: str = ""
    priority: ActionPriority = ActionPriority.MEDIUM
    category: ActionCategory = ActionCategory.PREVENTION
    due_days: int = 30
    details: str = ""


@router.post("/actions")
async def record_action(
    body: RecordActionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_action(**body.model_dump())
    return result.model_dump()


@router.get("/actions")
async def list_actions(
    incident_id: str | None = None,
    status: ActionStatus | None = None,
    assignee: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_actions(
            incident_id=incident_id, status=status, assignee=assignee, limit=limit
        )
    ]


@router.get("/actions/{record_id}")
async def get_action(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_action(record_id)
    if result is None:
        raise HTTPException(404, f"Action '{record_id}' not found")
    return result.model_dump()


@router.post("/actions/{record_id}/complete")
async def complete_action(
    record_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.complete_action(record_id)
    if result is None:
        raise HTTPException(404, f"Action '{record_id}' not found")
    return result.model_dump()


@router.get("/overdue")
async def identify_overdue_actions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overdue_actions()


@router.get("/completion-rate")
async def calculate_completion_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_completion_rate()


@router.get("/summary/{incident_id}")
async def summarize_incident_actions(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.summarize_incident_actions(incident_id)


@router.get("/assignee-rankings")
async def rank_assignees_by_completion(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_assignees_by_completion()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.clear_data()


pia_route = router
