"""Escalation Path Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.escalation_path import (
    BottleneckType,
    EscalationStage,
    PathEfficiency,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/escalation-path",
    tags=["Escalation Path"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Escalation path service unavailable")
    return _engine


class RecordPathRequest(BaseModel):
    path_id: str
    escalation_stage: EscalationStage = EscalationStage.L1_TRIAGE
    path_efficiency: PathEfficiency = PathEfficiency.ADEQUATE
    bottleneck_type: BottleneckType = BottleneckType.PROCESS
    resolution_time_minutes: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    path_id: str
    escalation_stage: EscalationStage = EscalationStage.L1_TRIAGE
    metric_value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/paths")
async def record_path(
    body: RecordPathRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_path(**body.model_dump())
    return result.model_dump()


@router.get("/paths")
async def list_paths(
    stage: EscalationStage | None = None,
    efficiency: PathEfficiency | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_paths(
            stage=stage,
            efficiency=efficiency,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/paths/{record_id}")
async def get_path(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_path(record_id)
    if result is None:
        raise HTTPException(404, f"Path record '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/efficiency")
async def analyze_path_efficiency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_path_efficiency()


@router.get("/inefficient-paths")
async def identify_inefficient_paths(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_inefficient_paths()


@router.get("/resolution-time-rankings")
async def rank_by_resolution_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_resolution_time()


@router.get("/trends")
async def detect_efficiency_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_efficiency_trends()


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


esp_route = router
