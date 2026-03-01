"""Dashboard Effectiveness Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.dashboard_effectiveness import (
    DashboardIssue,
    DashboardType,
    UsageFrequency,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/dashboard-effectiveness", tags=["Dashboard Effectiveness"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Dashboard effectiveness service unavailable")
    return _engine


class RecordDashboardRequest(BaseModel):
    dashboard_name: str
    dashboard_type: DashboardType = DashboardType.OPERATIONAL
    usage_frequency: UsageFrequency = UsageFrequency.WEEKLY
    dashboard_issue: DashboardIssue = DashboardIssue.STALE_DATA
    effectiveness_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    metric_name: str
    dashboard_type: DashboardType = DashboardType.OPERATIONAL
    view_count: int = 0
    avg_session_duration: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_dashboard(
    body: RecordDashboardRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_dashboard(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_dashboards(
    dashboard_type: DashboardType | None = None,
    frequency: UsageFrequency | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_dashboards(
            dashboard_type=dashboard_type,
            frequency=frequency,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_dashboard(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_dashboard(record_id)
    if result is None:
        raise HTTPException(404, f"Dashboard record '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/usage")
async def analyze_dashboard_usage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_dashboard_usage()


@router.get("/ineffective")
async def identify_ineffective_dashboards(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_ineffective_dashboards()


@router.get("/effectiveness-rankings")
async def rank_by_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_effectiveness()


@router.get("/usage-trends")
async def detect_usage_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_usage_trends()


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


des_route = router
