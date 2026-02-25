"""Metric cardinality manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.cardinality_manager import (
    CardinalityLevel,
    LabelAction,
    MetricType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/metric-cardinality",
    tags=["Metric Cardinality"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Metric cardinality service unavailable")
    return _engine


class RecordMetricRequest(BaseModel):
    metric_name: str
    metric_type: MetricType = MetricType.COUNTER
    cardinality: int = 0
    label_count: int = 0
    labels: list[str] = []
    details: str = ""


class AddRuleRequest(BaseModel):
    metric_pattern: str
    label_name: str
    action: LabelAction = LabelAction.KEEP
    reason: str = ""


@router.post("/metrics")
async def record_metric(
    body: RecordMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_metric(**body.model_dump())
    return result.model_dump()


@router.get("/metrics")
async def list_metrics(
    metric_name: str | None = None,
    level: CardinalityLevel | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_metrics(metric_name=metric_name, level=level, limit=limit)
    ]


@router.get("/metrics/{record_id}")
async def get_metric(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_metric(record_id)
    if result is None:
        raise HTTPException(404, f"Metric record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/high-cardinality")
async def detect_high_cardinality(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_high_cardinality()


@router.get("/recommendations/{metric_name}")
async def recommend_label_actions(
    metric_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.recommend_label_actions(metric_name)


@router.get("/growth-trends")
async def analyze_growth_trend(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_growth_trend()


@router.get("/label-culprits")
async def identify_label_culprits(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_label_culprits()


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


cm_route = router
