"""FinOps Intelligence API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

router = APIRouter()
_runner: Any | None = None


def set_runner(runner: Any) -> None:
    global _runner
    _runner = runner


@router.post("/finops/analyze")
async def start_analysis(
    session_id: str,
    analysis_config: dict[str, Any] | None = None,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Trigger FinOps intelligence analysis."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="FinOps Intelligence agent not initialized")
    result = await _runner.analyze(session_id=session_id, analysis_config=analysis_config or {})
    return {
        "session_id": result.session_id,
        "finding_count": result.finding_count,
        "savings_potential": result.savings_potential,
        "high_impact_count": result.high_impact_count,
        "plan_started": result.plan_started,
        "current_step": result.current_step,
        "error": result.error,
    }


@router.get("/finops/results")
async def list_results(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all FinOps analysis results."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="FinOps Intelligence agent not initialized")
    return {"results": _runner.list_results()}


@router.get("/finops/results/{session_id}")
async def get_result(
    session_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific FinOps analysis result."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="FinOps Intelligence agent not initialized")
    result = _runner.get_result(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return dict(result.model_dump())
