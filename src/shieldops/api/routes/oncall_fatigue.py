"""On-call fatigue analysis API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/oncall-fatigue",
    tags=["On-Call Fatigue"],
)

_analyzer: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _analyzer
    _analyzer = analyzer


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(503, "On-call fatigue service unavailable")
    return _analyzer


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordPageRequest(BaseModel):
    engineer: str
    service: str = ""
    urgency: str = "medium"
    time_of_day: str = "business_hours"
    acknowledged: bool = False
    resolution_minutes: float = 0.0


class TeamReportRequest(BaseModel):
    engineers: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/pages")
async def record_page(
    body: RecordPageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    event = analyzer.record_page(
        engineer=body.engineer,
        service=body.service,
        urgency=body.urgency,
        time_of_day=body.time_of_day,
        acknowledged=body.acknowledged,
        resolution_minutes=body.resolution_minutes,
    )
    return event.model_dump()


@router.get("/pages")
async def list_pages(
    engineer: str | None = None,
    urgency: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    events = analyzer.list_events(engineer=engineer, urgency=urgency, limit=limit)
    return [e.model_dump() for e in events]


@router.get("/fatigue/{engineer}")
async def get_fatigue(
    engineer: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    report = analyzer.analyze_fatigue(engineer)
    return report.model_dump()


@router.post("/team-report")
async def get_team_report(
    body: TeamReportRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    engineers = body.engineers if body.engineers else None
    reports = analyzer.get_team_report(engineers=engineers)
    return [r.model_dump() for r in reports]


@router.get("/burnout-risks")
async def get_burnout_risks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    risks = analyzer.get_burnout_risks()
    return [r.model_dump() for r in risks]


@router.get("/load-distribution")
async def get_load_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.get_load_distribution()


@router.get("/after-hours-ratio")
async def get_after_hours_ratio(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_after_hours_ratio()


@router.post("/clear")
async def clear_events(
    _user: Any = Depends(require_role("admin")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    count = analyzer.clear_events()
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
