"""Threat Automation API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

router = APIRouter()
_runner: Any | None = None


def set_runner(runner: Any) -> None:
    global _runner
    _runner = runner


@router.post("/threat-automation/hunt")
async def start_hunt(
    hunt_id: str,
    hunt_config: dict[str, Any] | None = None,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Trigger automated threat hunt."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="Threat Automation agent not initialized")
    result = await _runner.hunt(hunt_id=hunt_id, hunt_config=hunt_config or {})
    return {
        "hunt_id": result.hunt_id,
        "threat_count": result.threat_count,
        "critical_count": result.critical_count,
        "automated_responses": result.automated_responses,
        "current_step": result.current_step,
        "error": result.error,
    }


@router.get("/threat-automation/results")
async def list_results(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all threat automation hunt results."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="Threat Automation agent not initialized")
    return {"results": _runner.list_results()}


@router.get("/threat-automation/results/{session_id}")
async def get_result(
    session_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific threat automation hunt result."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="Threat Automation agent not initialized")
    result = _runner.get_result(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return dict(result.model_dump())
