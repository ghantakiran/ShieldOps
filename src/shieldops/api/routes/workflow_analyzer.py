"""Workflow Efficiency Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.workflow_analyzer import (
    BottleneckType,
    EfficiencyLevel,
    WorkflowType,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/workflow-analyzer", tags=["Workflow Analyzer"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Workflow analyzer service unavailable")
    return _engine


class RecordWorkflowRequest(BaseModel):
    workflow_id: str
    workflow_type: WorkflowType = WorkflowType.INCIDENT_RESPONSE
    efficiency_level: EfficiencyLevel = EfficiencyLevel.ACCEPTABLE
    bottleneck_type: BottleneckType = BottleneckType.MANUAL_STEP
    efficiency_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddStepRequest(BaseModel):
    step_pattern: str
    workflow_type: WorkflowType = WorkflowType.INCIDENT_RESPONSE
    duration_minutes: float = 0.0
    automation_pct: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_workflow(
    body: RecordWorkflowRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_workflow(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_workflows(
    workflow_type: WorkflowType | None = None,
    efficiency_level: EfficiencyLevel | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_workflows(
            workflow_type=workflow_type,
            efficiency_level=efficiency_level,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_workflow(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_workflow(record_id)
    if result is None:
        raise HTTPException(404, f"Workflow record '{record_id}' not found")
    return result.model_dump()


@router.post("/steps")
async def add_step(
    body: AddStepRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_step(**body.model_dump())
    return result.model_dump()


@router.get("/efficiency")
async def analyze_workflow_efficiency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_workflow_efficiency()


@router.get("/inefficient")
async def identify_inefficient_workflows(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_inefficient_workflows()


@router.get("/efficiency-rankings")
async def rank_by_efficiency_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_efficiency_score()


@router.get("/bottlenecks")
async def detect_workflow_bottlenecks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_workflow_bottlenecks()


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


wea_route = router
