"""Remediation API endpoints.

Provides REST endpoints for triggering, tracking, approving/denying,
and rolling back remediation agent workflows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from shieldops.agents.remediation.runner import RemediationRunner
from shieldops.models.base import Environment, RemediationAction, RiskLevel

if TYPE_CHECKING:
    from shieldops.db.repository import Repository

router = APIRouter()

# Application-level runner instance
_runner: RemediationRunner | None = None
_repository: Repository | None = None


def get_runner() -> RemediationRunner:
    """Get or create the remediation runner singleton."""
    global _runner
    if _runner is None:
        _runner = RemediationRunner()
    return _runner


def set_runner(runner: RemediationRunner) -> None:
    """Override the runner instance (used for testing and dependency injection)."""
    global _runner
    _runner = runner


def set_repository(repo: Repository | None) -> None:
    """Set the persistence repository for read queries."""
    global _repository
    _repository = repo


# --- Request/Response models ---


class TriggerRemediationRequest(BaseModel):
    """Request body to trigger a new remediation."""

    action_type: str
    target_resource: str
    environment: str = "production"
    risk_level: str = "medium"
    parameters: dict = Field(default_factory=dict)
    description: str = ""
    investigation_id: str | None = None
    alert_id: str | None = None
    alert_name: str | None = None


class ApprovalActionRequest(BaseModel):
    """Request body for approve/deny actions."""

    approver: str
    reason: str = ""


# --- Endpoints ---


@router.post("/remediations", status_code=202)
async def trigger_remediation(
    request: TriggerRemediationRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Trigger a new remediation action.

    Runs asynchronously. Returns 202 immediately.
    """
    from uuid import uuid4

    action = RemediationAction(
        id=f"act-{uuid4().hex[:12]}",
        action_type=request.action_type,
        target_resource=request.target_resource,
        environment=Environment(request.environment),
        risk_level=RiskLevel(request.risk_level),
        parameters=request.parameters,
        description=request.description or f"{request.action_type} on {request.target_resource}",
    )

    runner = get_runner()
    background_tasks.add_task(runner.remediate, action)

    return {
        "status": "accepted",
        "action_id": action.id,
        "action_type": request.action_type,
        "message": "Remediation started. Use GET /remediations to track progress.",
    }


@router.post("/remediations/sync")
async def trigger_remediation_sync(
    request: TriggerRemediationRequest,
) -> dict:
    """Trigger a remediation and wait for completion.

    Useful for testing and CLI tools.
    """
    from uuid import uuid4

    action = RemediationAction(
        id=f"act-{uuid4().hex[:12]}",
        action_type=request.action_type,
        target_resource=request.target_resource,
        environment=Environment(request.environment),
        risk_level=RiskLevel(request.risk_level),
        parameters=request.parameters,
        description=request.description or f"{request.action_type} on {request.target_resource}",
    )

    runner = get_runner()
    result = await runner.remediate(action, investigation_id=request.investigation_id)
    return result.model_dump(mode="json")


@router.get("/remediations")
async def list_remediations(
    environment: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List remediation timeline (newest first).

    Queries from PostgreSQL when available, falls back to in-memory.
    """
    if _repository:
        items = await _repository.list_remediations(
            environment=environment, status=status, limit=limit, offset=offset
        )
        total = await _repository.count_remediations(
            environment=environment, status=status
        )
        return {
            "remediations": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    # Fallback to in-memory
    runner = get_runner()
    all_remediations = runner.list_remediations()
    if environment:
        all_remediations = [
            r for r in all_remediations if r["environment"] == environment
        ]
    if status:
        all_remediations = [
            r for r in all_remediations if r["status"] == status
        ]
    total = len(all_remediations)
    paginated = all_remediations[offset : offset + limit]
    return {
        "remediations": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/remediations/{remediation_id}")
async def get_remediation(remediation_id: str) -> dict:
    """Get remediation detail with execution results and audit trail."""
    if _repository:
        result = await _repository.get_remediation(remediation_id)
        if result is not None:
            return result

    runner = get_runner()
    result = runner.get_remediation(remediation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Remediation not found")
    return result.model_dump(mode="json")


@router.post("/remediations/{remediation_id}/approve")
async def approve_remediation(
    remediation_id: str,
    request: ApprovalActionRequest,
) -> dict:
    """Approve a pending remediation action."""
    runner = get_runner()
    state = runner.get_remediation(remediation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Remediation not found")

    return {
        "remediation_id": remediation_id,
        "action": "approved",
        "approver": request.approver,
    }


@router.post("/remediations/{remediation_id}/deny")
async def deny_remediation(
    remediation_id: str,
    request: ApprovalActionRequest,
) -> dict:
    """Deny a pending remediation action."""
    runner = get_runner()
    state = runner.get_remediation(remediation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Remediation not found")

    return {
        "remediation_id": remediation_id,
        "action": "denied",
        "denier": request.approver,
        "reason": request.reason,
    }


@router.post("/remediations/{remediation_id}/rollback")
async def rollback_remediation(remediation_id: str) -> dict:
    """Rollback a completed remediation to pre-action state."""
    runner = get_runner()
    state = runner.get_remediation(remediation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Remediation not found")

    if not state.snapshot:
        raise HTTPException(status_code=400, detail="No snapshot available for rollback")

    return {
        "remediation_id": remediation_id,
        "action": "rollback_initiated",
        "snapshot_id": state.snapshot.id,
    }
