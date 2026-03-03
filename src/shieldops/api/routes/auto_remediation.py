"""Auto Remediation API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

router = APIRouter()
_runner: Any | None = None


def set_runner(runner: Any) -> None:
    global _runner
    _runner = runner


@router.post("/auto-remediation/execute")
async def start_execute(
    execute_id: str,
    remediation_config: dict[str, Any] | None = None,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Trigger auto remediation workflow."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="AutoRemediationRunner not initialized")
    cfg = remediation_config or {}
    result = await _runner.execute(execute_id=execute_id, remediation_config=cfg)
    return {
        "session_id": result.session_id,
        "current_step": result.current_step,
        "session_duration_ms": result.session_duration_ms,
        "error": result.error,
    }


@router.get("/auto-remediation/results")
async def list_results(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all auto remediation results."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="AutoRemediationRunner not initialized")
    return {"results": _runner.list_results()}


@router.get("/auto-remediation/results/{session_id}")
async def get_result(
    session_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific auto remediation result."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="AutoRemediationRunner not initialized")
    result = _runner.get_result(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return dict(result.model_dump())
