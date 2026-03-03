"""Zero Trust API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

router = APIRouter()
_runner: Any | None = None


def set_runner(runner: Any) -> None:
    global _runner
    _runner = runner


@router.post("/zero-trust/assess")
async def start_assessment(
    session_id: str,
    assessment_config: dict[str, Any] | None = None,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Trigger zero trust assessment."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="Zero Trust agent not initialized")
    result = await _runner.assess(session_id=session_id, assessment_config=assessment_config or {})
    return {
        "session_id": result.session_id,
        "identity_verified": result.identity_verified,
        "violation_count": result.violation_count,
        "trust_score": result.trust_score,
        "policy_enforced": result.policy_enforced,
        "current_step": result.current_step,
        "error": result.error,
    }


@router.get("/zero-trust/results")
async def list_results(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all zero trust assessment results."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="Zero Trust agent not initialized")
    return {"results": _runner.list_results()}


@router.get("/zero-trust/results/{session_id}")
async def get_result(
    session_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific zero trust assessment result."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="Zero Trust agent not initialized")
    result = _runner.get_result(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return dict(result.model_dump())
