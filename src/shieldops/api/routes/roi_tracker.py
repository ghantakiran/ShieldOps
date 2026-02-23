"""Agent ROI tracking API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/roi-tracker", tags=["ROI Tracker"])

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "ROI tracker service unavailable")
    return _tracker


class RecordImpactRequest(BaseModel):
    agent_id: str
    agent_type: str
    category: str
    description: str = ""
    monetary_value: float = 0.0
    time_saved_minutes: float = 0.0
    currency: str = "USD"
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/impacts")
async def record_impact(
    body: RecordImpactRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    entry = tracker.record_impact(**body.model_dump())
    return entry.model_dump()


@router.get("/entries")
async def list_entries(
    agent_type: str | None = None,
    category: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [
        e.model_dump()
        for e in tracker.list_entries(agent_type=agent_type, category=category, limit=limit)
    ]


@router.get("/report/{agent_type}")
async def get_agent_report(
    agent_type: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_agent_report(agent_type).model_dump()


@router.get("/summary")
async def get_summary(
    period: str = "",
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_summary(period=period).model_dump()


@router.get("/top-agents")
async def get_top_agents(
    limit: int = 10,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return tracker.get_top_agents(limit=limit)


@router.get("/categories")
async def get_category_breakdown(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, float]:
    tracker = _get_tracker()
    return tracker.get_category_breakdown()


@router.get("/time-series")
async def get_time_series(
    bucket_hours: int = 24,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return tracker.get_time_series(bucket_hours=bucket_hours)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
