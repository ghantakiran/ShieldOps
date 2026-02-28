"""Remediation pipeline orchestrator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.remediation_pipeline import (
    PipelineStage,
    PipelineStatus,
    StepDependency,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/remediation-pipeline",
    tags=["Remediation Pipeline"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Remediation pipeline service unavailable")
    return _engine


class RecordPipelineRequest(BaseModel):
    pipeline_name: str
    pipeline_stage: PipelineStage = PipelineStage.VALIDATION
    pipeline_status: PipelineStatus = PipelineStatus.QUEUED
    step_dependency: StepDependency = StepDependency.SEQUENTIAL
    step_count: int = 0
    details: str = ""


class AddStepRequest(BaseModel):
    step_name: str
    pipeline_stage: PipelineStage = PipelineStage.EXECUTION
    pipeline_status: PipelineStatus = PipelineStatus.RUNNING
    duration_seconds: float = 0.0


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
    pipeline_status: PipelineStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_pipelines(
            pipeline_name=pipeline_name,
            pipeline_status=pipeline_status,
            limit=limit,
        )
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


@router.post("/steps")
async def add_step(
    body: AddStepRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_step(**body.model_dump())
    return result.model_dump()


@router.get("/efficiency/{pipeline_name}")
async def analyze_pipeline_efficiency(
    pipeline_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_pipeline_efficiency(pipeline_name)


@router.get("/failed-pipelines")
async def identify_failed_pipelines(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failed_pipelines()


@router.get("/rankings")
async def rank_by_completion_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_completion_rate()


@router.get("/bottlenecks")
async def detect_pipeline_bottlenecks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_pipeline_bottlenecks()


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


rpo_route = router
