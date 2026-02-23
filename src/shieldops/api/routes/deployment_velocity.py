"""Deployment velocity tracking API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/deployment-velocity",
    tags=["Deployment Velocity"],
)

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Deployment velocity service unavailable")
    return _tracker


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordDeploymentRequest(BaseModel):
    service: str
    team: str = ""
    stage: str = "production"
    duration_seconds: float = 0.0
    success: bool = True
    commit_sha: str = ""
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/events")
async def record_deployment(
    body: RecordDeploymentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    event = tracker.record_deployment(
        service=body.service,
        team=body.team,
        stage=body.stage,
        duration_seconds=body.duration_seconds,
        success=body.success,
        commit_sha=body.commit_sha,
        tags=body.tags,
    )
    return event.model_dump()


@router.get("/events")
async def list_events(
    service: str | None = None,
    team: str | None = None,
    stage: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    events = tracker.list_events(service=service, team=team, stage=stage, limit=limit)
    return [e.model_dump() for e in events]


@router.get("/velocity")
async def get_velocity(
    service: str | None = None,
    team: str | None = None,
    period_days: int | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    report = tracker.get_velocity(service=service, team=team, period_days=period_days)
    return report.model_dump()


@router.get("/trend/{service}")
async def get_trend(
    service: str,
    period_days: int | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_trend(service=service, period_days=period_days)


@router.get("/bottlenecks")
async def identify_bottlenecks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return tracker.identify_bottlenecks()


@router.get("/compare")
async def compare_teams(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return tracker.compare_teams()


@router.get("/leaderboard")
async def get_leaderboard(
    limit: int = 10,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return tracker.get_leaderboard(limit=limit)


@router.post("/clear")
async def clear_events(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    count = tracker.clear_events()
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
