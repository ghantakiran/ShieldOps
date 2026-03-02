"""Metric Collection Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.metric_collection_optimizer import (
    CollectionStatus,
    MetricTier,
    OptimizationStrategy,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/metric-collection-optimizer",
    tags=["Metric Collection Optimizer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Metric collection optimizer service unavailable")
    return _engine


class RecordCollectionRequest(BaseModel):
    metric_name: str
    collection_status: CollectionStatus = CollectionStatus.OPTIMAL
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.REDUCE_FREQUENCY
    metric_tier: MetricTier = MetricTier.REAL_TIME
    efficiency_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAnalysisRequest(BaseModel):
    metric_name: str
    collection_status: CollectionStatus = CollectionStatus.OPTIMAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/collections")
async def record_collection(
    body: RecordCollectionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_collection(**body.model_dump())
    return result.model_dump()


@router.get("/collections")
async def list_collections(
    collection_status: CollectionStatus | None = None,
    optimization_strategy: OptimizationStrategy | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_collections(
            collection_status=collection_status,
            optimization_strategy=optimization_strategy,
            team=team,
            limit=limit,
        )
    ]


@router.get("/collections/{record_id}")
async def get_collection(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_collection(record_id)
    if result is None:
        raise HTTPException(404, f"Collection '{record_id}' not found")
    return result.model_dump()


@router.post("/analyses")
async def add_analysis(
    body: AddAnalysisRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_analysis(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_collection_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_collection_distribution()


@router.get("/inefficient-collections")
async def identify_inefficient_collections(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_inefficient_collections()


@router.get("/efficiency-rankings")
async def rank_by_efficiency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_efficiency()


@router.get("/trends")
async def detect_collection_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_collection_trends()


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


mco_route = router
