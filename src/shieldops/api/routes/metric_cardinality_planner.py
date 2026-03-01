"""Metric Cardinality Planner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.metric_cardinality_planner import (
    CardinalityLevel,
    MetricSource,
    ReductionStrategy,
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


class RecordCardinalityRequest(BaseModel):
    metric_name: str
    cardinality_level: CardinalityLevel = CardinalityLevel.LOW
    metric_source: MetricSource = MetricSource.APPLICATION
    reduction_strategy: ReductionStrategy = ReductionStrategy.KEEP
    cardinality_count: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddPlanRequest(BaseModel):
    metric_name: str
    cardinality_level: CardinalityLevel = CardinalityLevel.LOW
    plan_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/cardinalities")
async def record_cardinality(
    body: RecordCardinalityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_cardinality(**body.model_dump())
    return result.model_dump()


@router.get("/cardinalities")
async def list_cardinalities(
    level: CardinalityLevel | None = None,
    source: MetricSource | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_cardinalities(
            level=level,
            source=source,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/cardinalities/{record_id}")
async def get_cardinality(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_cardinality(record_id)
    if result is None:
        raise HTTPException(404, f"Cardinality record '{record_id}' not found")
    return result.model_dump()


@router.post("/plans")
async def add_plan(
    body: AddPlanRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_plan(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_cardinality_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_cardinality_distribution()


@router.get("/high-cardinality")
async def identify_high_cardinality_metrics(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_cardinality_metrics()


@router.get("/cardinality-rankings")
async def rank_by_cardinality(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_cardinality()


@router.get("/trends")
async def detect_cardinality_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_cardinality_trends()


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


mcp_route = router
