"""Compliance Dashboard API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance_dashboard.models import (
    ComplianceFramework,
    ControlStatus,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/compliance", tags=["Compliance Dashboard"])

_dashboard: Any = None


def set_dashboard(dash: Any) -> None:
    """Inject the ComplianceDashboard instance."""
    global _dashboard
    _dashboard = dash


def _get_dashboard() -> Any:
    if _dashboard is None:
        raise HTTPException(503, "Compliance dashboard service unavailable")
    return _dashboard


# -------------------------------------------------------------------
# Request / response models
# -------------------------------------------------------------------


class TriggerCollectionRequest(BaseModel):
    framework: ComplianceFramework
    interval_hours: int = 24


class AssessControlRequest(BaseModel):
    features: list[str] | None = None


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------


@router.get("/summary/{framework}")
async def get_compliance_summary(
    framework: ComplianceFramework,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Return compliance posture summary for a framework."""
    dash = _get_dashboard()
    summary = await dash.get_summary(framework)
    result: dict[str, Any] = summary.model_dump()
    return result


@router.get("/controls")
async def list_controls(
    framework: ComplianceFramework = Query(ComplianceFramework.SOC2),
    status: ControlStatus | None = Query(None),
    category: str | None = Query(None),
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    """List controls with optional status/category filters."""
    dash = _get_dashboard()
    controls = await dash.get_controls(
        framework,
        status_filter=status,
        category_filter=category,
    )
    return [c.model_dump() for c in controls]


@router.get("/controls/{control_id}")
async def get_control_detail(
    control_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Return a single control with its evidence records."""
    dash = _get_dashboard()
    mapper = dash.soc2_mapper
    ctrl = mapper.get_control(control_id)
    if ctrl is None:
        raise HTTPException(404, f"Control '{control_id}' not found")
    evidence = dash.evidence_collector.list_evidence_for_control(control_id)
    return {
        "control": ctrl.model_dump(),
        "evidence": [e.model_dump() for e in evidence],
    }


@router.post("/assess/{control_id}")
async def assess_control(
    control_id: str,
    body: AssessControlRequest | None = None,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Trigger auto-assessment for a control."""
    dash = _get_dashboard()
    mapper = dash.soc2_mapper
    if body and body.features:
        mapper.set_active_features(body.features)
    try:
        ctrl = await mapper.assess_control(control_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    result: dict[str, Any] = ctrl.model_dump()
    return result


@router.get("/evidence/{control_id}")
async def get_evidence_for_control(
    control_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    """Return all evidence records for a control."""
    dash = _get_dashboard()
    records = dash.evidence_collector.list_evidence_for_control(control_id)
    return [r.model_dump() for r in records]


@router.post("/evidence/collect")
async def trigger_evidence_collection(
    body: TriggerCollectionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Schedule periodic evidence collection for a framework."""
    dash = _get_dashboard()
    schedule = await dash.evidence_collector.schedule_evidence_collection(
        body.framework,
        interval_hours=body.interval_hours,
    )
    result: dict[str, Any] = schedule
    return result


@router.get("/report/{framework}")
async def export_compliance_report(
    framework: ComplianceFramework,
    fmt: str = Query("markdown"),
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    """Export a compliance report in the given format."""
    dash = _get_dashboard()
    report = await dash.export_report(framework, fmt=fmt)
    return {"framework": framework, "format": fmt, "report": report}


@router.get("/gap-analysis/{framework}")
async def get_gap_analysis(
    framework: ComplianceFramework,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    """Return gap analysis for the given framework."""
    dash = _get_dashboard()
    if framework == ComplianceFramework.SOC2:
        gaps: list[dict[str, Any]] = await dash.soc2_mapper.get_gap_analysis()
        return gaps
    return []
