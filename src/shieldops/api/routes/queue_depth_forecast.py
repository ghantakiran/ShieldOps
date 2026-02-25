"""Queue depth forecaster routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.queue_depth_forecast import (
    BacklogTrend,
    OverflowRisk,
    QueueType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/queue-depth-forecast",
    tags=["Queue Depth Forecast"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Queue depth forecast service unavailable")
    return _engine


class RecordDepthRequest(BaseModel):
    queue_name: str
    queue_type: QueueType = QueueType.KAFKA
    current_depth: int = 0
    consumer_count: int = 0
    producer_rate: float = 0.0
    consumer_rate: float = 0.0
    trend: BacklogTrend = BacklogTrend.STABLE
    details: str = ""


class CreateForecastRequest(BaseModel):
    queue_name: str
    predicted_depth: int = 0
    overflow_risk: OverflowRisk = OverflowRisk.NONE
    time_to_overflow_minutes: float = 0.0
    recommended_consumers: int = 0
    details: str = ""


@router.post("/depths")
async def record_depth(
    body: RecordDepthRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_depth(**body.model_dump())
    return result.model_dump()


@router.get("/depths")
async def list_depths(
    queue_name: str | None = None,
    queue_type: QueueType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_depths(queue_name=queue_name, queue_type=queue_type, limit=limit)
    ]


@router.get("/depths/{record_id}")
async def get_depth(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_depth(record_id)
    if result is None:
        raise HTTPException(404, f"Depth record '{record_id}' not found")
    return result.model_dump()


@router.post("/forecasts")
async def create_forecast(
    body: CreateForecastRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.create_forecast(**body.model_dump())
    return result.model_dump()


@router.get("/health/{queue_name}")
async def analyze_queue_health(
    queue_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_queue_health(queue_name)


@router.get("/at-risk")
async def identify_at_risk_queues(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_at_risk_queues()


@router.get("/backlog-growth")
async def rank_by_backlog_growth(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_backlog_growth()


@router.get("/consumer-scaling")
async def estimate_consumer_scaling(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.estimate_consumer_scaling()


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


qdf_route = router
