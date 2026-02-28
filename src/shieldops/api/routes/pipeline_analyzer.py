"""Deployment pipeline analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.pipeline_analyzer import (
    BottleneckType,
    PipelineHealth,
    PipelineStage,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/pipeline-analyzer",
    tags=["Pipeline Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Pipeline analyzer service unavailable")
    return _engine


class RecordPipelineRequest(BaseModel):
    pipeline_name: str
    stage: PipelineStage = PipelineStage.BUILD
    bottleneck: BottleneckType = BottleneckType.QUEUE_WAIT
    health: PipelineHealth = PipelineHealth.HEALTHY
    duration_minutes: float = 0.0
    details: str = ""


class AddStageMetricRequest(BaseModel):
    metric_name: str
    stage: PipelineStage = PipelineStage.BUILD
    bottleneck: BottleneckType = BottleneckType.QUEUE_WAIT
    avg_duration_minutes: float = 0.0
    failure_rate_pct: float = 0.0


@router.post("/pipelines")
async def record_pipeline(
    body: RecordPipelineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_pipeline(**body.model_dump())
    return result.model_dump()


@router.get("/pipelines")
async def list_pipelines(
    pipeline_name: str | None = None,
    stage: PipelineStage | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_pipelines(pipeline_name=pipeline_name, stage=stage, limit=limit)
    ]


@router.get("/pipelines/{record_id}")
async def get_pipeline(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_pipeline(record_id)
    if result is None:
        raise HTTPException(404, f"Pipeline '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_stage_metric(
    body: AddStageMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_stage_metric(**body.model_dump())
    return result.model_dump()


@router.get("/health/{pipeline_name}")
async def analyze_pipeline_health(
    pipeline_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_pipeline_health(pipeline_name)


@router.get("/bottlenecks")
async def identify_bottlenecks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_bottlenecks()


@router.get("/rankings")
async def rank_by_throughput(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_throughput()


@router.get("/trends")
async def detect_pipeline_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_pipeline_trends()


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


dpa_route = router
