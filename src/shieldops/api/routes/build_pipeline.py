"""Build pipeline analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.build_pipeline import (
    BuildOutcome,
    OptimizationTarget,
    PipelineStage,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/build-pipeline",
    tags=["Build Pipeline"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Build pipeline service unavailable")
    return _engine


class RecordBuildRequest(BaseModel):
    pipeline_name: str
    stage: PipelineStage = PipelineStage.BUILD
    outcome: BuildOutcome = BuildOutcome.SUCCESS
    duration_seconds: float = 0.0
    branch: str = ""
    commit_sha: str = ""
    is_flaky: bool = False
    details: str = ""


class AddOptimizationRequest(BaseModel):
    pipeline_name: str
    target: OptimizationTarget = OptimizationTarget.CACHING
    estimated_savings_seconds: float = 0.0
    reason: str = ""


@router.post("/builds")
async def record_build(
    body: RecordBuildRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_build(**body.model_dump())
    return result.model_dump()


@router.get("/builds")
async def list_builds(
    pipeline_name: str | None = None,
    outcome: BuildOutcome | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_builds(pipeline_name=pipeline_name, outcome=outcome, limit=limit)
    ]


@router.get("/builds/{record_id}")
async def get_build(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_build(record_id)
    if result is None:
        raise HTTPException(404, f"Build record '{record_id}' not found")
    return result.model_dump()


@router.post("/optimizations")
async def add_optimization(
    body: AddOptimizationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_optimization(**body.model_dump())
    return result.model_dump()


@router.get("/performance/{pipeline_name}")
async def analyze_pipeline_performance(
    pipeline_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_pipeline_performance(pipeline_name)


@router.get("/flaky-stages")
async def identify_flaky_stages(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_flaky_stages()


@router.get("/slowest")
async def rank_slowest_pipelines(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_slowest_pipelines()


@router.get("/time-savings")
async def estimate_time_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.estimate_time_savings()


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


bp_route = router
