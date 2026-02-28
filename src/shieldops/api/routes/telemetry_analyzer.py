"""Telemetry analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.agents.telemetry_analyzer import (
    AnalysisScope,
    PerformanceTier,
    TelemetryMetric,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/telemetry-analyzer",
    tags=["Telemetry Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Telemetry analyzer service unavailable")
    return _engine


class RecordTelemetryRequest(BaseModel):
    agent_name: str
    telemetry_metric: TelemetryMetric = TelemetryMetric.LATENCY
    performance_tier: PerformanceTier = PerformanceTier.GOOD
    analysis_scope: AnalysisScope = AnalysisScope.DAILY
    metric_value: float = 0.0
    details: str = ""


class AddBaselineRequest(BaseModel):
    baseline_name: str
    telemetry_metric: TelemetryMetric = TelemetryMetric.TOKEN_USAGE
    performance_tier: PerformanceTier = PerformanceTier.ACCEPTABLE
    threshold_value: float = 0.0


@router.post("/telemetry")
async def record_telemetry(
    body: RecordTelemetryRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_telemetry(**body.model_dump())
    return result.model_dump()


@router.get("/telemetry")
async def list_telemetry(
    agent_name: str | None = None,
    telemetry_metric: TelemetryMetric | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_telemetry(
            agent_name=agent_name, telemetry_metric=telemetry_metric, limit=limit
        )
    ]


@router.get("/telemetry/{record_id}")
async def get_telemetry(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_telemetry(record_id)
    if result is None:
        raise HTTPException(404, f"Telemetry '{record_id}' not found")
    return result.model_dump()


@router.post("/baselines")
async def add_baseline(
    body: AddBaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_baseline(**body.model_dump())
    return result.model_dump()


@router.get("/performance/{agent_name}")
async def analyze_agent_performance(
    agent_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_agent_performance(agent_name)


@router.get("/underperforming")
async def identify_underperforming_agents(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_underperforming_agents()


@router.get("/rankings")
async def rank_by_efficiency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_efficiency()


@router.get("/degradation")
async def detect_performance_degradation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_performance_degradation()


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


ata_route = router
