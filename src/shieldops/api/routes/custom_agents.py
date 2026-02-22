"""Custom Agent Builder API endpoints.

Provides CRUD operations for custom workflow definitions, execution triggers,
and run status retrieval. Uses the module-level ``set_builder()`` pattern
consistent with other ShieldOps route modules.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.agents.custom.builder import (
    CreateWorkflowRequest,
    CustomAgentBuilder,
    UpdateWorkflowRequest,
)
from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

logger = structlog.get_logger()

router = APIRouter(prefix="/agents/custom", tags=["Custom Agents"])

# ------------------------------------------------------------------
# Module-level singleton -- wired from app.py lifespan
# ------------------------------------------------------------------

_builder: CustomAgentBuilder | None = None


def set_builder(builder: CustomAgentBuilder) -> None:
    """Inject the CustomAgentBuilder instance (called from app.py)."""
    global _builder
    _builder = builder


def _get_builder() -> CustomAgentBuilder:
    if _builder is None:
        raise HTTPException(
            status_code=503,
            detail="Custom agent builder not configured",
        )
    return _builder


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------


class RunWorkflowRequest(BaseModel):
    """Optional variables to pass when executing a workflow."""

    variables: dict[str, Any] = Field(default_factory=dict)


class ValidationResponse(BaseModel):
    """Result of workflow validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("")
async def create_workflow(
    body: CreateWorkflowRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Create a new custom workflow definition."""
    builder = _get_builder()
    try:
        workflow = builder.create_workflow(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"workflow": workflow.model_dump(mode="json")}


@router.get("")
async def list_workflows(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all custom workflow definitions."""
    builder = _get_builder()
    workflows = builder.list_workflows()
    return {
        "workflows": [w.model_dump(mode="json") for w in workflows],
        "total": len(workflows),
    }


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific workflow definition."""
    builder = _get_builder()
    workflow = builder.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"workflow": workflow.model_dump(mode="json")}


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    body: UpdateWorkflowRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Update an existing workflow definition."""
    builder = _get_builder()
    try:
        workflow = builder.update_workflow(workflow_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"workflow": workflow.model_dump(mode="json")}


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Delete a workflow definition (admin only)."""
    builder = _get_builder()
    deleted = builder.delete_workflow(workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"deleted": True, "workflow_id": workflow_id}


@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    body: RunWorkflowRequest | None = None,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Execute a workflow with optional runtime variables."""
    builder = _get_builder()
    if builder.get_workflow(workflow_id) is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    variables = body.variables if body else {}
    try:
        run = await builder.run_workflow(workflow_id, variables)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run": run.model_dump(mode="json")}


@router.get("/{workflow_id}/runs")
async def list_workflow_runs(
    workflow_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all runs for a specific workflow."""
    builder = _get_builder()
    if builder.get_workflow(workflow_id) is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    runs = builder.list_runs(workflow_id=workflow_id)
    return {
        "runs": [r.model_dump(mode="json") for r in runs],
        "total": len(runs),
    }


@router.post("/{workflow_id}/validate")
async def validate_workflow(
    workflow_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> ValidationResponse:
    """Validate a stored workflow without executing it."""
    builder = _get_builder()
    workflow = builder.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    errors = builder.validate_workflow(workflow)
    return ValidationResponse(valid=len(errors) == 0, errors=errors)


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the status and results of a specific workflow run."""
    builder = _get_builder()
    run = builder.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run": run.model_dump(mode="json")}
