"""Runbook execution engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/runbook-engine",
    tags=["Runbook Engine"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Runbook engine service unavailable")
    return _engine


class StartExecutionRequest(BaseModel):
    runbook_name: str
    trigger: str = "manual"
    initiated_by: str = ""
    context: dict[str, Any] | None = None


class RecordStepRequest(BaseModel):
    name: str = ""
    outcome: str = "success"
    duration_seconds: float = 0.0
    output: str = ""


@router.post("/executions")
async def start_execution(
    body: StartExecutionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    execution = engine.start_execution(
        runbook_name=body.runbook_name,
        trigger=body.trigger,
        initiated_by=body.initiated_by,
        context=body.context,
    )
    return execution.model_dump()


@router.get("/executions")
async def list_executions(
    runbook_name: str | None = None,
    status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    execs = engine.list_executions(runbook_name=runbook_name, status=status, limit=limit)
    return [e.model_dump() for e in execs]


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    execution = engine.get_execution(execution_id)
    if execution is None:
        raise HTTPException(404, f"Execution '{execution_id}' not found")
    return execution.model_dump()


@router.post("/executions/{execution_id}/steps")
async def record_step(
    execution_id: str,
    body: RecordStepRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    step = engine.record_step(
        execution_id=execution_id,
        name=body.name,
        outcome=body.outcome,
        duration_seconds=body.duration_seconds,
        output=body.output,
    )
    if step is None:
        raise HTTPException(404, f"Execution '{execution_id}' not found")
    return step.model_dump()


@router.post("/executions/{execution_id}/pause")
async def pause_execution(
    execution_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    if not engine.pause_execution(execution_id):
        raise HTTPException(400, "Cannot pause execution")
    return {"paused": True}


@router.post("/executions/{execution_id}/resume")
async def resume_execution(
    execution_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    if not engine.resume_execution(execution_id):
        raise HTTPException(400, "Cannot resume execution")
    return {"resumed": True}


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    if not engine.cancel_execution(execution_id):
        raise HTTPException(400, "Cannot cancel execution")
    return {"cancelled": True}


@router.post("/executions/{execution_id}/complete")
async def complete_execution(
    execution_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    if not engine.complete_execution(execution_id):
        raise HTTPException(400, "Cannot complete execution")
    return {"completed": True}


@router.get("/success-rate")
async def get_success_rate(
    runbook_name: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_success_rate(runbook_name=runbook_name)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
