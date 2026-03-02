"""SOC Analyst API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

router = APIRouter()
_runner: Any | None = None


def set_runner(runner: Any) -> None:
    global _runner
    _runner = runner


@router.post("/soc/analyze")
async def analyze_alert(
    alert_id: str,
    alert_data: dict[str, Any] | None = None,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Trigger SOC analysis on an alert."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="SOC Analyst agent not initialized")
    result = await _runner.analyze(alert_id=alert_id, alert_data=alert_data or {})
    return {
        "alert_id": result.alert_id,
        "tier": result.tier,
        "triage_score": result.triage_score,
        "should_suppress": result.should_suppress,
        "mitre_techniques": result.mitre_techniques,
        "attack_narrative": result.attack_narrative,
        "containment_recommendations": [r.model_dump() for r in result.containment_recommendations],
        "playbook_executed": result.playbook_executed,
        "current_step": result.current_step,
        "error": result.error,
    }


@router.get("/soc/results")
async def list_results(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all SOC analysis results."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="SOC Analyst agent not initialized")
    return {"results": _runner.list_results()}


@router.get("/soc/results/{session_id}")
async def get_result(
    session_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific SOC analysis result."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="SOC Analyst agent not initialized")
    result = _runner.get_result(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.model_dump()  # type: ignore[no-any-return]
