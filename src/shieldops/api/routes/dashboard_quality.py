"""Dashboard quality scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.dashboard_quality import (
    DashboardAction,
    DashboardGrade,
    QualityDimension,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dashboard-quality",
    tags=["Dashboard Quality"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Dashboard quality service unavailable")
    return _engine


class RecordDashboardRequest(BaseModel):
    dashboard_name: str
    owner: str = ""
    load_time_ms: float = 0.0
    panel_count: int = 0
    query_count: int = 0
    usage_count_30d: int = 0
    last_modified_days_ago: int = 0
    details: str = ""


class RecordIssueRequest(BaseModel):
    dashboard_name: str
    dimension: QualityDimension = QualityDimension.LOAD_TIME
    action: DashboardAction = DashboardAction.NO_ACTION
    description: str = ""
    severity: str = "medium"


@router.post("/dashboards")
async def record_dashboard(
    body: RecordDashboardRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_dashboard(**body.model_dump())
    return result.model_dump()


@router.get("/dashboards")
async def list_dashboards(
    dashboard_name: str | None = None,
    grade: DashboardGrade | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_dashboards(dashboard_name=dashboard_name, grade=grade, limit=limit)
    ]


@router.get("/dashboards/{record_id}")
async def get_dashboard(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_dashboard(record_id)
    if result is None:
        raise HTTPException(404, f"Dashboard record '{record_id}' not found")
    return result.model_dump()


@router.post("/issues")
async def record_issue(
    body: RecordIssueRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_issue(**body.model_dump())
    return result.model_dump()


@router.get("/score/{dashboard_name}")
async def score_dashboard(
    dashboard_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.score_dashboard(dashboard_name)


@router.get("/stale")
async def identify_stale_dashboards(
    stale_days: int = 180,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_stale_dashboards(stale_days=stale_days)


@router.get("/rankings")
async def rank_dashboards_by_quality(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_dashboards_by_quality()


@router.get("/query-efficiency")
async def analyze_query_efficiency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_query_efficiency()


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


dq_route = router
