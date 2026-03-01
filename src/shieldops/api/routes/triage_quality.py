"""Triage Quality Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.triage_quality import (
    TriageAccuracy,
    TriageOutcome,
    TriageSpeed,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/triage-quality", tags=["Triage Quality"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Triage quality service unavailable")
    return _engine


class RecordTriageRequest(BaseModel):
    incident_id: str
    triage_accuracy: TriageAccuracy = TriageAccuracy.UNVERIFIED
    triage_speed: TriageSpeed = TriageSpeed.NORMAL
    triage_outcome: TriageOutcome = TriageOutcome.RESOLVED_QUICKLY
    quality_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    metric_name: str
    triage_accuracy: TriageAccuracy = TriageAccuracy.UNVERIFIED
    quality_threshold: float = 0.0
    avg_quality_score: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_triage(
    body: RecordTriageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_triage(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_triages(
    accuracy: TriageAccuracy | None = None,
    speed: TriageSpeed | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_triages(
            accuracy=accuracy,
            speed=speed,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_triage(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_triage(record_id)
    if result is None:
        raise HTTPException(404, f"Triage record '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/accuracy")
async def analyze_triage_accuracy(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_triage_accuracy()


@router.get("/poor-triages")
async def identify_poor_triages(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_poor_triages()


@router.get("/quality-rankings")
async def rank_by_quality_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_quality_score()


@router.get("/trends")
async def detect_triage_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_triage_trends()


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


tqa_route = router
