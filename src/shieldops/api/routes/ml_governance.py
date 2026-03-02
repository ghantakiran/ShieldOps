"""ML Governance API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

router = APIRouter()
_runner: Any | None = None


def set_runner(runner: Any) -> None:
    global _runner
    _runner = runner


@router.post("/ml-governance/evaluate")
async def start_evaluation(
    audit_id: str,
    audit_config: dict[str, Any] | None = None,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Trigger ML governance evaluation."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="ML Governance agent not initialized")
    result = await _runner.evaluate(audit_id=audit_id, audit_config=audit_config or {})
    return {
        "audit_id": result.session_id,
        "audit_count": result.audit_count,
        "critical_count": result.critical_count,
        "risk_score": result.risk_score,
        "action_started": result.action_started,
        "current_step": result.current_step,
        "error": result.error,
    }


@router.get("/ml-governance/results")
async def list_results(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all ML governance evaluation results."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="ML Governance agent not initialized")
    return {"results": _runner.list_results()}


@router.get("/ml-governance/results/{session_id}")
async def get_result(
    session_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific ML governance evaluation result."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="ML Governance agent not initialized")
    result = _runner.get_result(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return dict(result.model_dump())
