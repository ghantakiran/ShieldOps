"""Threat Response Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.threat_response_tracker import (
    ResponseEffectiveness,
    ResponseStatus,
    ThreatCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/threat-response-tracker",
    tags=["Threat Response Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Threat response tracker service unavailable")
    return _engine


class RecordResponseRequest(BaseModel):
    threat_id: str
    threat_category: ThreatCategory = ThreatCategory.MALWARE
    response_status: ResponseStatus = ResponseStatus.INVESTIGATING
    response_effectiveness: ResponseEffectiveness = ResponseEffectiveness.ADEQUATE
    response_time_hours: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    threat_id: str
    threat_category: ThreatCategory = ThreatCategory.MALWARE
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/responses")
async def record_response(
    body: RecordResponseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_response(**body.model_dump())
    return result.model_dump()


@router.get("/responses")
async def list_responses(
    threat_category: ThreatCategory | None = None,
    response_status: ResponseStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_responses(
            threat_category=threat_category,
            response_status=response_status,
            team=team,
            limit=limit,
        )
    ]


@router.get("/responses/{record_id}")
async def get_response(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_response(record_id)
    if result is None:
        raise HTTPException(404, f"Response '{record_id}' not found")
    return result.model_dump()


@router.post("/assessments")
async def add_assessment(
    body: AddAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_response_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_response_distribution()


@router.get("/slow-responses")
async def identify_slow_responses(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_slow_responses()


@router.get("/response-time-rankings")
async def rank_by_response_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_response_time()


@router.get("/trends")
async def detect_response_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_response_trends()


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


trt_route = router
