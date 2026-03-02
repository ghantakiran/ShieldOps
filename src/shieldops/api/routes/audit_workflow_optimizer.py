"""Audit Workflow Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.audit_workflow_optimizer import (
    BottleneckType,
    OptimizationType,
    WorkflowStage,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/audit-workflow-optimizer",
    tags=["Audit Workflow Optimizer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Audit workflow optimizer service unavailable")
    return _engine


class RecordWorkflowRequest(BaseModel):
    workflow_name: str
    workflow_stage: WorkflowStage = WorkflowStage.EVIDENCE_COLLECTION
    bottleneck_type: BottleneckType = BottleneckType.MANUAL_HANDOFF
    optimization_type: OptimizationType = OptimizationType.PARALLELIZE
    cycle_time_hours: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAnalysisRequest(BaseModel):
    workflow_name: str
    workflow_stage: WorkflowStage = WorkflowStage.EVIDENCE_COLLECTION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/workflows")
async def record_workflow(
    body: RecordWorkflowRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_workflow(**body.model_dump())
    return result.model_dump()


@router.get("/workflows")
async def list_workflows(
    workflow_stage: WorkflowStage | None = None,
    bottleneck_type: BottleneckType | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_workflows(
            workflow_stage=workflow_stage,
            bottleneck_type=bottleneck_type,
            team=team,
            limit=limit,
        )
    ]


@router.get("/workflows/{record_id}")
async def get_workflow(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_workflow(record_id)
    if result is None:
        raise HTTPException(404, f"Workflow record '{record_id}' not found")
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
async def analyze_workflow_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_workflow_distribution()


@router.get("/long-cycles")
async def identify_long_cycle_workflows(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_long_cycle_workflows()


@router.get("/cycle-time-rankings")
async def rank_by_cycle_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_cycle_time()


@router.get("/trends")
async def detect_workflow_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_workflow_trends()


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


awo_route = router
