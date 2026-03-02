"""Attack Surface API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

router = APIRouter()
_runner: Any | None = None


def set_runner(runner: Any) -> None:
    global _runner
    _runner = runner


@router.post("/attack-surface/scan")
async def start_scan(
    scan_id: str,
    scan_config: dict[str, Any] | None = None,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Trigger attack surface scan."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="Attack Surface agent not initialized")
    result = await _runner.scan(scan_id=scan_id, scan_config=scan_config or {})
    return {
        "scan_id": result.scan_id,
        "asset_count": result.asset_count,
        "critical_count": result.critical_count,
        "risk_score": result.risk_score,
        "remediation_started": result.remediation_started,
        "current_step": result.current_step,
        "error": result.error,
    }


@router.get("/attack-surface/results")
async def list_results(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all attack surface scan results."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="Attack Surface agent not initialized")
    return {"results": _runner.list_results()}


@router.get("/attack-surface/results/{session_id}")
async def get_result(
    session_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific attack surface scan result."""
    if _runner is None:
        raise HTTPException(status_code=503, detail="Attack Surface agent not initialized")
    result = _runner.get_result(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")
    return dict(result.model_dump())
