"""Incident response time analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.response_time import (
    ResponsePhase,
    ResponseSpeed,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/response-time",
    tags=["Response Time"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Response time service unavailable")
    return _engine


class RecordResponseRequest(BaseModel):
    incident_id: str
    phase: ResponsePhase = ResponsePhase.DETECTION
    response_minutes: float = 0.0
    speed: ResponseSpeed = ResponseSpeed.ACCEPTABLE
    team: str = ""
    service: str = ""
    details: str = ""


class AddBreakdownRequest(BaseModel):
    incident_id: str
    phase: ResponsePhase = ResponsePhase.DETECTION
    start_minutes: float = 0.0
    end_minutes: float = 0.0
    duration_minutes: float = 0.0


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
    phase: ResponsePhase | None = None,
    speed: ResponseSpeed | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_responses(phase=phase, speed=speed, team=team, limit=limit)
    ]


@router.get("/responses/{record_id}")
async def get_response(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_response(record_id)
    if result is None:
        raise HTTPException(404, f"Response record '{record_id}' not found")
    return result.model_dump()


@router.post("/breakdowns")
async def add_breakdown(
    body: AddBreakdownRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_breakdown(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/by-phase")
async def analyze_response_by_phase(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_response_by_phase()


@router.get("/slow")
async def identify_slow_responses(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_slow_responses()


@router.get("/rankings")
async def rank_by_response_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_response_time()


@router.get("/trends")
async def detect_response_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
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


rta_route = router
