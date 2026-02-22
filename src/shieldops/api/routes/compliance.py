"""SOC2 Compliance API endpoints.

Provides compliance audit reports, control inspection, evidence
collection, trend tracking, and admin override capabilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from shieldops.api.auth.dependencies import get_current_user, require_role
from shieldops.api.auth.models import UserResponse, UserRole

if TYPE_CHECKING:
    from shieldops.compliance.soc2 import SOC2ComplianceEngine

logger = structlog.get_logger()

router = APIRouter()

# ------------------------------------------------------------------
# Module-level singleton -- wired from app.py lifespan
# ------------------------------------------------------------------

_engine: SOC2ComplianceEngine | None = None


def set_engine(engine: SOC2ComplianceEngine) -> None:
    """Set the compliance engine instance (called during app startup)."""
    global _engine
    _engine = engine


def _get_engine() -> SOC2ComplianceEngine:
    if _engine is None:
        raise HTTPException(
            status_code=503,
            detail="Compliance engine not initialized",
        )
    return _engine


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------


class OverrideRequest(BaseModel):
    """Request body to override a control status."""

    status: str
    justification: str


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("/compliance/report")
async def get_compliance_report(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Run a full SOC2 compliance audit and return the report."""
    engine = _get_engine()
    report = await engine.run_audit()
    return report.model_dump(mode="json")


@router.get("/compliance/controls")
async def list_controls(
    category: str | None = Query(None, description="Filter by trust service category"),
    status: str | None = Query(None, description="Filter by control status"),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """List all SOC2 controls with optional filters."""
    engine = _get_engine()
    controls = await engine.get_controls(category=category, status=status)
    return {
        "controls": [c.model_dump(mode="json") for c in controls],
        "total": len(controls),
    }


@router.get("/compliance/controls/{control_id}")
async def get_control(
    control_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get details for a single compliance control."""
    engine = _get_engine()
    try:
        check = await engine.check_control(control_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Control '{control_id}' not found",
        ) from None
    return check.model_dump(mode="json")


@router.get("/compliance/trends")
async def get_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days for trend data"),
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get compliance score trend data."""
    engine = _get_engine()
    trend = await engine.get_trends(days=days)
    return trend.model_dump(mode="json")


@router.get("/compliance/evidence/{control_id}")
async def get_evidence(
    control_id: str,
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Get evidence collected for a specific control."""
    engine = _get_engine()
    try:
        evidence = await engine.get_evidence(control_id)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Control '{control_id}' not found",
        ) from None
    return {
        "control_id": control_id,
        "evidence": evidence,
        "total": len(evidence),
    }


@router.post("/compliance/controls/{control_id}/override")
async def override_control(
    control_id: str,
    body: OverrideRequest,
    user: UserResponse = Depends(require_role(UserRole.ADMIN)),
) -> dict[str, Any]:
    """Admin override a control status with justification."""
    engine = _get_engine()

    valid_statuses = {"pass", "fail", "warning", "not_applicable"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Must be one of: {sorted(valid_statuses)}",
        )

    if not body.justification.strip():
        raise HTTPException(
            status_code=400,
            detail="Justification is required for overrides",
        )

    try:
        control = await engine.override_control(
            control_id=control_id,
            new_status=body.status,
            justification=body.justification,
            admin_user=user.id,
        )
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Control '{control_id}' not found",
        ) from None

    logger.info(
        "compliance_control_overridden",
        control_id=control_id,
        new_status=body.status,
        admin=user.id,
    )
    return control.model_dump(mode="json")
