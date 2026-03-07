"""API routes for Kubernetes remediation actions.

Provides REST endpoints to execute K8s remediation actions with OPA policy gates,
retrieve action status, trigger rollbacks, and inspect snapshots.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role
from shieldops.api.auth.models import UserResponse, UserRole
from shieldops.remediation.k8s_actions import K8sRemediationExecutor
from shieldops.remediation.models import (
    K8sActionType,
    K8sRemediationRequest,
    RemediationResult,
    ResourceSnapshot,
)

router = APIRouter()

# Application-level executor instance
_executor: K8sRemediationExecutor | None = None


def get_executor() -> K8sRemediationExecutor:
    """Get or create the K8s remediation executor singleton."""
    global _executor
    if _executor is None:
        _executor = K8sRemediationExecutor()
    return _executor


def set_executor(executor: K8sRemediationExecutor) -> None:
    """Override the executor instance (used for testing and dependency injection)."""
    global _executor
    _executor = executor


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------


class ExecuteActionRequest(BaseModel):
    """Request body to execute a Kubernetes remediation action."""

    action_type: K8sActionType
    namespace: str
    resource_name: str
    environment: str = "production"
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    investigation_id: str | None = None


class RollbackActionRequest(BaseModel):
    """Request body to rollback a remediation action."""

    reason: str = ""


class ActionResponse(BaseModel):
    """Standardized response wrapper for remediation actions."""

    status: str
    action_id: str
    message: str
    result: RemediationResult | None = None


class SnapshotResponse(BaseModel):
    """Response wrapper for snapshot details."""

    snapshot_id: str
    snapshot: ResourceSnapshot | None = None
    message: str = ""


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/remediation/actions", status_code=200)
async def execute_action(
    request: ExecuteActionRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> ActionResponse:
    """Execute a Kubernetes remediation action with policy gate evaluation.

    The action goes through the full lifecycle:
    1. OPA policy evaluation
    2. Pre-action snapshot
    3. Action execution
    4. Health verification
    5. Automatic rollback on health failure

    Returns the complete RemediationResult synchronously.
    """
    executor = get_executor()

    remediation_request = K8sRemediationRequest(
        action_type=request.action_type,
        namespace=request.namespace,
        resource_name=request.resource_name,
        environment=request.environment,
        parameters=request.parameters,
        description=request.description
        or (f"{request.action_type} on {request.namespace}/{request.resource_name}"),
        initiated_by=_user.email if hasattr(_user, "email") else "api_user",
        investigation_id=request.investigation_id,
    )

    result = await executor.execute(remediation_request)

    return ActionResponse(
        status=result.status,
        action_id=result.id,
        message=result.message,
        result=result,
    )


@router.get("/remediation/actions/{action_id}")
async def get_action_status(
    action_id: str,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)),
) -> ActionResponse:
    """Get the status and details of a remediation action."""
    executor = get_executor()
    result = executor.get_result(action_id)

    if result is None:
        raise HTTPException(status_code=404, detail=f"Action {action_id} not found")

    return ActionResponse(
        status=result.status,
        action_id=result.id,
        message=result.message,
        result=result,
    )


@router.post("/remediation/actions/{action_id}/rollback")
async def rollback_action(
    action_id: str,
    request: RollbackActionRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> ActionResponse:
    """Rollback a previously executed remediation action to its pre-action state.

    Requires that the action has an associated snapshot.
    """
    executor = get_executor()

    try:
        result = await executor.rollback_action(action_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if request.reason:
        result.audit_log.append(f"Rollback reason: {request.reason}")

    return ActionResponse(
        status=result.status,
        action_id=result.id,
        message=result.message,
        result=result,
    )


@router.get("/remediation/snapshots/{snapshot_id}")
async def get_snapshot_details(
    snapshot_id: str,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)),
) -> SnapshotResponse:
    """Get details of a resource snapshot captured before a remediation action."""
    executor = get_executor()
    snapshot = executor.get_snapshot(snapshot_id)

    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")

    return SnapshotResponse(
        snapshot_id=snapshot.id,
        snapshot=snapshot,
        message="Snapshot found",
    )
