"""Incident Response API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

router = APIRouter()
_runner: Any | None = None


def set_runner(runner: Any) -> None:
    global _runner
    _runner = runner


@router.post("/incident-response/respond")
async def respond_to_incident(
    incident_id: str,
    incident_data: dict[str, Any] | None = None,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Trigger incident response workflow."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="Incident Response agent not initialized")
    result = await _runner.respond(incident_id=incident_id, incident_data=incident_data or {})
    return {
        "incident_id": result.incident_id,
        "severity": result.severity,
        "assessment_score": result.assessment_score,
        "containment_complete": result.containment_complete,
        "eradication_complete": result.eradication_complete,
        "recovery_complete": result.recovery_complete,
        "validation_passed": result.validation_passed,
        "current_step": result.current_step,
        "error": result.error,
    }


@router.get("/incident-response/results")
async def list_results(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all incident response results."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="Incident Response agent not initialized")
    return {"results": _runner.list_results()}


@router.get("/incident-response/results/{session_id}")
async def get_result(
    session_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific incident response result."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="Incident Response agent not initialized")
    result = _runner.get_result(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return dict(result.model_dump())
