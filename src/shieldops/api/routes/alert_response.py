"""Alert Response Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.alert_response import (
    AlertOutcome,
    ResponseAction,
    ResponseSpeed,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/alert-response", tags=["Alert Response"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Alert response analyzer service unavailable")
    return _engine


class RecordResponseRequest(BaseModel):
    alert_id: str
    response_action: ResponseAction = ResponseAction.ACKNOWLEDGED
    response_speed: ResponseSpeed = ResponseSpeed.NORMAL
    alert_outcome: AlertOutcome = AlertOutcome.TRUE_POSITIVE
    response_time_minutes: float = 0.0
    responder: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    metric_name: str
    response_action: ResponseAction = ResponseAction.ACKNOWLEDGED
    avg_response_time: float = 0.0
    total_responses: int = 0
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
    response_action: ResponseAction | None = None,
    response_speed: ResponseSpeed | None = None,
    responder: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_responses(
            response_action=response_action,
            response_speed=response_speed,
            responder=responder,
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


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/response-times")
async def analyze_response_times(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_response_times()


@router.get("/slow-responses")
async def identify_slow_responses(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_slow_responses()


@router.get("/speed-rankings")
async def rank_by_response_speed(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_response_speed()


@router.get("/trends")
async def detect_response_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_response_patterns()


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


ara_route = router
