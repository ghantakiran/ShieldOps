"""Orchestration API routes — workflow execution and alert handling."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import get_current_user
from shieldops.api.auth.models import UserResponse
from shieldops.orchestration.models import EscalationPolicy
from shieldops.orchestration.supervisor import SupervisorAgent
from shieldops.orchestration.workflow_engine import WorkflowEngine

router = APIRouter()

# Module-level singletons — configured at app startup via set_engine()
_engine: WorkflowEngine | None = None
_supervisor: SupervisorAgent | None = None


def set_engine(engine: WorkflowEngine) -> None:
    """Configure the workflow engine used by these routes."""
    global _engine, _supervisor  # noqa: PLW0603
    _engine = engine
    _supervisor = SupervisorAgent(engine=engine)


# ------------------------------------------------------------------
# Request / response schemas
# ------------------------------------------------------------------


class RunWorkflowRequest(BaseModel):
    """Request body for triggering a workflow."""

    workflow_name: str
    trigger: str = "manual"
    params: dict[str, Any] = Field(default_factory=dict)


class AlertRequest(BaseModel):
    """Request body for an incoming alert."""

    alert_name: str
    namespace: str = "default"
    severity: str = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------


@router.post("/workflows/run")
async def run_workflow(
    body: RunWorkflowRequest,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger a named workflow."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Workflow engine not configured")
    try:
        run = await _engine.execute_workflow(
            workflow_name=body.workflow_name,
            trigger=body.trigger,
            params=body.params,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return run.model_dump(mode="json")


@router.get("/workflows/runs")
async def list_runs(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all active workflow runs."""
    if _supervisor is None:
        raise HTTPException(status_code=503, detail="Supervisor not configured")
    runs = await _supervisor.get_active_runs()
    return {
        "runs": [r.model_dump(mode="json") for r in runs],
        "total": len(runs),
    }


@router.get("/workflows/runs/{run_id}")
async def get_run(
    run_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get details of a specific workflow run."""
    if _supervisor is None:
        raise HTTPException(status_code=503, detail="Supervisor not configured")
    runs = await _supervisor.get_active_runs()
    for run in runs:
        if run.run_id == run_id:
            return run.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Run not found")


@router.post("/workflows/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Cancel an active workflow run."""
    if _supervisor is None:
        raise HTTPException(status_code=503, detail="Supervisor not configured")
    cancelled = await _supervisor.cancel_run(run_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "cancelled": True}


@router.post("/alerts")
async def handle_alert(
    body: AlertRequest,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Handle an incoming alert — triggers the supervisor."""
    if _supervisor is None:
        raise HTTPException(status_code=503, detail="Supervisor not configured")
    try:
        run = await _supervisor.handle_alert(
            alert_name=body.alert_name,
            namespace=body.namespace,
            severity=body.severity,
            metadata=body.metadata,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return run.model_dump(mode="json")


@router.get("/policies")
async def list_policies(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all configured escalation policies."""
    if _supervisor is None:
        raise HTTPException(status_code=503, detail="Supervisor not configured")
    policies: list[EscalationPolicy] = _supervisor.get_policies()
    return {
        "policies": [p.model_dump(mode="json") for p in policies],
        "total": len(policies),
    }
