"""Data pipeline reliability monitor routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.data_pipeline import (
    DataQualityIssue,
    PipelineHealth,
    PipelineType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/data-pipeline",
    tags=["Data Pipeline"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Data pipeline service unavailable")
    return _engine


class RecordRunRequest(BaseModel):
    pipeline_name: str
    pipeline_type: PipelineType = PipelineType.BATCH
    health: PipelineHealth = PipelineHealth.HEALTHY
    records_processed: int = 0
    duration_seconds: float = 0.0
    freshness_seconds: float = 0.0
    details: str = ""


class RecordQualityIssueRequest(BaseModel):
    pipeline_name: str
    issue_type: DataQualityIssue = DataQualityIssue.SCHEMA_DRIFT
    affected_records: int = 0
    severity: float = 0.0
    details: str = ""


@router.post("/runs")
async def record_run(
    body: RecordRunRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_run(**body.model_dump())
    return result.model_dump()


@router.get("/runs")
async def list_runs(
    pipeline_name: str | None = None,
    health: PipelineHealth | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_runs(pipeline_name=pipeline_name, health=health, limit=limit)
    ]


@router.get("/runs/{record_id}")
async def get_run(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_run(record_id)
    if result is None:
        raise HTTPException(404, f"Run record '{record_id}' not found")
    return result.model_dump()


@router.post("/quality-issues")
async def record_quality_issue(
    body: RecordQualityIssueRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_quality_issue(**body.model_dump())
    return result.model_dump()


@router.get("/health/{pipeline_name}")
async def analyze_pipeline_health(
    pipeline_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_pipeline_health(pipeline_name)


@router.get("/stale")
async def identify_stale_pipelines(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_stale_pipelines()


@router.get("/error-rate-rankings")
async def rank_by_error_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_error_rate()


@router.get("/schema-drifts")
async def detect_schema_drifts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_schema_drifts()


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


dpr_route = router
