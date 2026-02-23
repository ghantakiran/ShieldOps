"""Capacity trends analysis API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/capacity-trends", tags=["Capacity Trends"])

_analyzer: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _analyzer
    _analyzer = analyzer


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(503, "Capacity trends service unavailable")
    return _analyzer


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordSnapshotRequest(BaseModel):
    service: str
    resource_type: str
    current_usage: float
    total_capacity: float
    unit: str = ""


class AnalyzeTrendsRequest(BaseModel):
    resource_type: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/snapshots")
async def record_snapshot(
    body: RecordSnapshotRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    snap = analyzer.record_snapshot(
        service=body.service,
        resource_type=body.resource_type,
        used=body.current_usage,
        total=body.total_capacity,
    )
    return snap.model_dump()


@router.post("/analyze/{service}")
async def analyze_trends(
    service: str,
    body: AnalyzeTrendsRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    if body.resource_type is not None:
        analysis = analyzer.analyze_trend(
            service=service,
            resource_type=body.resource_type,
        )
        return [analysis.model_dump()]
    # Analyze all resource types that have snapshots for this service
    resource_types: set[str] = set()
    for snap in analyzer._snapshots:
        if snap.service == service:
            resource_types.add(snap.resource_type)
    results: list[dict[str, Any]] = []
    for rt in sorted(resource_types):
        analysis = analyzer.analyze_trend(
            service=service,
            resource_type=rt,
        )
        results.append(analysis.model_dump())
    return results


@router.get("/snapshots")
async def list_snapshots(
    service: str | None = None,
    resource_type: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [
        s.model_dump()
        for s in analyzer.get_snapshots(
            service=service,
            resource_type=resource_type,
            limit=limit,
        )
    ]


@router.get("/trends")
async def list_trends(
    service: str | None = None,
    direction: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [
        a.model_dump()
        for a in analyzer.list_analyses(
            service=service,
            direction=direction,
        )
    ]


@router.get("/trends/{trend_id}")
async def get_trend(
    trend_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    analysis = analyzer.get_analysis(trend_id)
    if analysis is None:
        raise HTTPException(404, f"Trend '{trend_id}' not found")
    return analysis.model_dump()


@router.get("/alerts")
async def list_exhaustion_alerts(
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    at_risk = analyzer.get_at_risk_resources()
    if service is not None:
        at_risk = [a for a in at_risk if a.service == service]
    return [a.model_dump() for a in at_risk]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
