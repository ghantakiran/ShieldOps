"""Observability Intelligence API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

router = APIRouter()
_runner: Any | None = None


def set_runner(runner: Any) -> None:
    global _runner
    _runner = runner


@router.post("/observability-intelligence/analyze")
async def start_analysis(
    analyze_id: str,
    analyze_config: dict[str, Any] | None = None,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Trigger observability intelligence analysis."""
    if _runner is None:
        raise HTTPException(
            status_code=503, detail="Observability Intelligence agent not initialized"
        )
    result = await _runner.analyze(analyze_id=analyze_id, analyze_config=analyze_config or {})
    return {
        "session_id": result.session_id,
        "current_step": result.current_step,
        "session_duration_ms": result.session_duration_ms,
        "error": result.error,
    }


@router.get("/observability-intelligence/results")
async def list_results(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all observability intelligence results."""
    if _runner is None:
        raise HTTPException(
            status_code=503, detail="Observability Intelligence agent not initialized"
        )
    return {"results": _runner.list_results()}


@router.get("/observability-intelligence/results/{session_id}")
async def get_result(
    session_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific observability intelligence result."""
    if _runner is None:
        raise HTTPException(
            status_code=503, detail="Observability Intelligence agent not initialized"
        )
    result = _runner.get_result(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return dict(result.model_dump())
