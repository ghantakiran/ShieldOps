"""Runbook execution tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.runbook_exec_tracker import (
    ExecutionMode,
    ExecutionPhase,
    ExecutionResult,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/runbook-exec-tracker",
    tags=["Runbook Execution Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Runbook execution tracker service unavailable")
    return _engine


class RecordExecutionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    runbook_id: str
    result: ExecutionResult = ExecutionResult.SUCCESS
    mode: ExecutionMode = ExecutionMode.MANUAL
    duration_minutes: float = 0.0
    team: str = ""
    service: str = ""
    details: str = ""


class AddStepRequest(BaseModel):
    model_config = {"extra": "forbid"}

    execution_id: str
    phase: ExecutionPhase = ExecutionPhase.EXECUTION
    step_name: str = ""
    duration_minutes: float = 0.0
    success: bool = True


@router.post("/executions")
async def record_execution(
    body: RecordExecutionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_execution(**body.model_dump())
    return result.model_dump()


@router.get("/executions")
async def list_executions(
    result: ExecutionResult | None = None,
    mode: ExecutionMode | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_executions(result=result, mode=mode, team=team, limit=limit)
    ]


@router.get("/executions/{record_id}")
async def get_execution(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rec = engine.get_execution(record_id)
    if rec is None:
        raise HTTPException(404, f"Execution record '{record_id}' not found")
    return rec.model_dump()


@router.post("/steps")
async def add_step(
    body: AddStepRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_step(**body.model_dump())
    return result.model_dump()


@router.get("/success-analysis")
async def analyze_execution_success(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_execution_success()


@router.get("/failing")
async def identify_failing_runbooks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failing_runbooks()


@router.get("/rankings")
async def rank_by_duration(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_duration()


@router.get("/trends")
async def detect_execution_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_execution_trends()


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


ret_route = router
