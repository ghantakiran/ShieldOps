"""SLO monitoring API routes."""

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from shieldops.observability.slo_monitor import SLODefinition, SLOMonitor

logger = structlog.get_logger()
router = APIRouter(prefix="/slo", tags=["SLO"])

_monitor: SLOMonitor | None = None


def set_monitor(monitor: SLOMonitor) -> None:
    global _monitor
    _monitor = monitor


def _get_monitor() -> SLOMonitor:
    if _monitor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SLO monitor not initialized",
        )
    return _monitor


class CreateSLORequest(BaseModel):
    name: str
    description: str = ""
    target: float = 0.999
    window_days: int = 30
    sli_type: str = "availability"


@router.get("")
async def list_slos() -> dict[str, Any]:
    """Get all SLO statuses with error budgets."""
    monitor = _get_monitor()
    budgets = monitor.get_all_budgets()
    return {
        "slos": [b.model_dump() for b in budgets],
        "total": len(budgets),
    }


@router.get("/{name}")
async def get_slo(name: str) -> dict[str, Any]:
    """Get SLO detail with error budget."""
    monitor = _get_monitor()
    budget = monitor.get_error_budget(name)
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SLO '{name}' not found",
        )
    slo = monitor.get_slo(name)
    return {
        "definition": slo.model_dump() if slo else {},
        "budget": budget.model_dump(),
    }


@router.post("")
async def create_slo(request: CreateSLORequest) -> dict[str, Any]:
    """Create a custom SLO."""
    monitor = _get_monitor()
    slo = SLODefinition(
        name=request.name,
        description=request.description,
        target=request.target,
        window_days=request.window_days,
        sli_type=request.sli_type,
    )
    monitor.register_slo(slo)
    return {"slo": slo.model_dump(), "status": "created"}


@router.get("/{name}/burn-rate")
async def get_burn_rate(name: str) -> dict[str, Any]:
    """Get burn rate history for an SLO."""
    monitor = _get_monitor()
    if monitor.get_slo(name) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SLO '{name}' not found",
        )
    history = monitor.get_burn_rate_history(name)
    return {"slo_name": name, "burn_rate_history": history}
