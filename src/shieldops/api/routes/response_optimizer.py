"""Incident Response Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.response_optimizer import (
    EscalationLevel,
    ResponseEfficiency,
    ResponsePhase,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/response-optimizer", tags=["Response Optimizer"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Response optimizer service unavailable")
    return _engine


class RecordResponseRequest(BaseModel):
    incident_id: str
    response_phase: ResponsePhase = ResponsePhase.DETECTION
    response_efficiency: ResponseEfficiency = ResponseEfficiency.ADEQUATE
    escalation_level: EscalationLevel = EscalationLevel.L1
    response_time_minutes: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddPatternRequest(BaseModel):
    phase_pattern: str
    response_phase: ResponsePhase = ResponsePhase.DETECTION
    efficiency_threshold: float = 0.0
    avg_time_minutes: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_response(
    body: RecordResponseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_response(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_responses(
    phase: ResponsePhase | None = None,
    efficiency: ResponseEfficiency | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_responses(
            phase=phase,
            efficiency=efficiency,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_response(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_response(record_id)
    if result is None:
        raise HTTPException(404, f"Response record '{record_id}' not found")
    return result.model_dump()


@router.post("/patterns")
async def add_pattern(
    body: AddPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_pattern(**body.model_dump())
    return result.model_dump()


@router.get("/efficiency")
async def analyze_response_efficiency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_response_efficiency()


@router.get("/bottlenecks")
async def identify_bottlenecks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_bottlenecks()


@router.get("/time-rankings")
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


iro_route = router
