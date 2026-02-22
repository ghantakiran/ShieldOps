"""SLA Management API endpoints.

Provides CRUD for SLO definitions, error budget inspection,
downtime recording, breach history, and an aggregate dashboard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

if TYPE_CHECKING:
    from shieldops.sla.engine import SLAEngine

logger = structlog.get_logger()

router = APIRouter(prefix="/sla", tags=["SLA"])

# ------------------------------------------------------------------
# Module-level singleton -- wired from app.py lifespan
# ------------------------------------------------------------------

_engine: SLAEngine | None = None


def set_engine(engine: SLAEngine) -> None:
    """Set the SLA engine instance (called during app startup)."""
    global _engine
    _engine = engine


def _get_engine() -> SLAEngine:
    if _engine is None:
        raise HTTPException(
            status_code=503,
            detail="SLA engine not initialized",
        )
    return _engine


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------


class DowntimeRequest(BaseModel):
    """Request body for recording a downtime event."""

    slo_id: str
    duration_minutes: float
    description: str = ""


# ------------------------------------------------------------------
# SLO CRUD Endpoints
# ------------------------------------------------------------------


@router.post("/slos")
async def create_slo(
    body: dict[str, Any],
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Create a new SLO definition (admin only)."""
    from shieldops.sla.engine import SLOCreateRequest

    engine = _get_engine()
    request = SLOCreateRequest(**body)
    slo = engine.create_slo(request)
    return slo.model_dump(mode="json")


@router.get("/slos")
async def list_slos(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all SLO definitions."""
    engine = _get_engine()
    slos = engine.list_slos()
    return {
        "slos": [s.model_dump(mode="json") for s in slos],
        "total": len(slos),
    }


@router.get("/slos/{slo_id}")
async def get_slo(
    slo_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific SLO definition."""
    engine = _get_engine()
    slo = engine.get_slo(slo_id)
    if slo is None:
        raise HTTPException(status_code=404, detail="SLO not found")
    return slo.model_dump(mode="json")


@router.put("/slos/{slo_id}")
async def update_slo(
    slo_id: str,
    body: dict[str, Any],
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Update an existing SLO definition (admin only)."""
    from shieldops.sla.engine import SLOUpdateRequest

    engine = _get_engine()
    request = SLOUpdateRequest(**body)
    slo = engine.update_slo(slo_id, request)
    if slo is None:
        raise HTTPException(status_code=404, detail="SLO not found")
    return slo.model_dump(mode="json")


@router.delete("/slos/{slo_id}")
async def delete_slo(
    slo_id: str,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Delete an SLO definition (admin only)."""
    engine = _get_engine()
    deleted = engine.delete_slo(slo_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="SLO not found")
    return {"deleted": True, "slo_id": slo_id}


# ------------------------------------------------------------------
# Error Budget Endpoints
# ------------------------------------------------------------------


@router.get("/budgets")
async def list_budgets(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get error budgets for all SLOs."""
    engine = _get_engine()
    slos = engine.list_slos()
    budgets = []
    for slo in slos:
        budget = engine.calculate_error_budget(slo.id)
        budgets.append(budget.model_dump(mode="json"))
    return {"budgets": budgets, "total": len(budgets)}


@router.get("/budgets/{slo_id}")
async def get_budget(
    slo_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get error budget for a specific SLO."""
    engine = _get_engine()
    slo = engine.get_slo(slo_id)
    if slo is None:
        raise HTTPException(status_code=404, detail="SLO not found")
    budget = engine.calculate_error_budget(slo_id)
    return budget.model_dump(mode="json")


# ------------------------------------------------------------------
# Downtime & Breach Endpoints
# ------------------------------------------------------------------


@router.post("/downtime")
async def record_downtime(
    body: DowntimeRequest,
    _user: UserResponse = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> dict[str, Any]:
    """Record a downtime event against an SLO."""
    engine = _get_engine()
    try:
        breach = engine.record_downtime(
            slo_id=body.slo_id,
            duration_minutes=body.duration_minutes,
            description=body.description,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="SLO not found") from None
    return breach.model_dump(mode="json")


@router.get("/breaches")
async def list_breaches(
    slo_id: str | None = Query(default=None, description="Filter by SLO ID"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get SLA breach history."""
    engine = _get_engine()
    breaches = engine.get_breaches(slo_id=slo_id, limit=limit)
    return {
        "breaches": [b.model_dump(mode="json") for b in breaches],
        "total": len(breaches),
    }


# ------------------------------------------------------------------
# Dashboard Endpoint
# ------------------------------------------------------------------


@router.get("/dashboard")
async def get_dashboard(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the aggregate SLA dashboard."""
    engine = _get_engine()
    dashboard = engine.get_dashboard()
    return dashboard.model_dump(mode="json")
