"""Toil measurement tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/toil-tracker",
    tags=["Toil Tracker"],
)

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Toil tracker service unavailable")
    return _tracker


class RecordToilRequest(BaseModel):
    team: str
    category: str = "manual_deployment"
    description: str = ""
    duration_minutes: float = 0.0
    engineer: str = ""
    automated: bool = False


@router.post("/entries")
async def record_toil(
    body: RecordToilRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    entry = tracker.record_toil(
        team=body.team,
        category=body.category,
        description=body.description,
        duration_minutes=body.duration_minutes,
        engineer=body.engineer,
        automated=body.automated,
    )
    return entry.model_dump()


@router.get("/entries")
async def list_entries(
    team: str | None = None,
    category: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    entries = tracker.list_entries(team=team, category=category, limit=limit)
    return [e.model_dump() for e in entries]


@router.get("/entries/{entry_id}")
async def get_entry(
    entry_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    entry = tracker.get_entry(entry_id)
    if entry is None:
        raise HTTPException(404, f"Entry '{entry_id}' not found")
    return entry.model_dump()


@router.post("/summary/{team}")
async def compute_summary(
    team: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.compute_summary(team).model_dump()


@router.get("/candidates")
async def get_candidates(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    candidates = tracker.identify_automation_candidates()
    return [c.model_dump() for c in candidates]


@router.get("/trend/{team}")
async def get_trend(
    team: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    trend = tracker.get_toil_trend(team)
    return {"team": team, "trend": trend}


@router.get("/ranking")
async def get_ranking(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return tracker.get_team_ranking()


@router.get("/savings")
async def get_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.compute_automation_savings()


@router.delete("/entries")
async def clear_entries(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    count = tracker.clear_entries()
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
