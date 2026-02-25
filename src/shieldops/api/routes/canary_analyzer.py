"""Canary analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.canary_analyzer import (
    CanaryDecision,
    CanaryMetricType,
    CanaryPhase,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/canary-analyzer",
    tags=["Canary Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Canary analyzer service unavailable",
        )
    return _engine


class CreateAnalysisRequest(BaseModel):
    deployment_id: str
    service_name: str
    canary_version: str
    baseline_version: str
    traffic_pct: float = 5.0


class CompareMetricsRequest(BaseModel):
    metric_type: CanaryMetricType
    canary_value: float
    baseline_value: float


class AdvancePhaseRequest(BaseModel):
    phase: CanaryPhase


@router.post("/analyses")
async def create_analysis(
    body: CreateAnalysisRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    analysis = engine.create_analysis(**body.model_dump())
    return analysis.model_dump()


@router.get("/analyses")
async def list_analyses(
    service_name: str | None = None,
    decision: CanaryDecision | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        a.model_dump()
        for a in engine.list_analyses(
            service_name=service_name,
            decision=decision,
            limit=limit,
        )
    ]


@router.get("/analyses/{analysis_id}")
async def get_analysis(
    analysis_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    analysis = engine.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(404, f"Analysis '{analysis_id}' not found")
    return analysis.model_dump()


@router.post("/analyses/{analysis_id}/compare")
async def compare_metrics(
    analysis_id: str,
    body: CompareMetricsRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    comparison = engine.compare_metrics(
        analysis_id,
        body.metric_type,
        body.canary_value,
        body.baseline_value,
    )
    return comparison.model_dump()


@router.post("/analyses/{analysis_id}/decide")
async def decide_promotion(
    analysis_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.decide_promotion(analysis_id)
    if result.get("error"):
        raise HTTPException(404, f"Analysis '{analysis_id}' not found")
    return result


@router.post("/analyses/{analysis_id}/phase")
async def advance_phase(
    analysis_id: str,
    body: AdvancePhaseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.advance_phase(analysis_id, body.phase)
    if result.get("error"):
        raise HTTPException(404, f"Analysis '{analysis_id}' not found")
    return result


@router.get("/promotion-rate")
async def get_promotion_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_promotion_rate()


@router.get("/flaky-services")
async def get_flaky_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_flaky_services()


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_canary_report()
    return report.model_dump()


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


ca_route = router
