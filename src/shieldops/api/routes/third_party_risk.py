"""Third-party vendor risk tracking API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/third-party-risk", tags=["Third Party Risk"])

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Third-party risk service unavailable")
    return _tracker


class RegisterVendorRequest(BaseModel):
    name: str
    category: str
    compliance_certifications: list[str] = Field(default_factory=list)
    contact_email: str = ""
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssessVendorRequest(BaseModel):
    risk_level: str
    findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    assessed_by: str = ""


class ReportIncidentRequest(BaseModel):
    title: str
    description: str = ""
    severity: str = "medium"
    impact: str = ""


@router.post("/vendors")
async def register_vendor(
    body: RegisterVendorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    vendor = tracker.register_vendor(**body.model_dump())
    return vendor.model_dump()


@router.get("/vendors")
async def list_vendors(
    risk_level: str | None = None,
    category: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [v.model_dump() for v in tracker.list_vendors(risk_level=risk_level, category=category)]


@router.get("/vendors/{vendor_id}")
async def get_vendor(
    vendor_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    vendor = tracker.get_vendor(vendor_id)
    if vendor is None:
        raise HTTPException(404, f"Vendor '{vendor_id}' not found")
    return vendor.model_dump()


@router.delete("/vendors/{vendor_id}")
async def delete_vendor(
    vendor_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    tracker = _get_tracker()
    if not tracker.delete_vendor(vendor_id):
        raise HTTPException(404, f"Vendor '{vendor_id}' not found")
    return {"status": "deleted"}


@router.post("/vendors/{vendor_id}/assess")
async def assess_vendor(
    vendor_id: str,
    body: AssessVendorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    assessment = tracker.assess_vendor(vendor_id=vendor_id, **body.model_dump())
    return assessment.model_dump()


@router.post("/vendors/{vendor_id}/incidents")
async def report_incident(
    vendor_id: str,
    body: ReportIncidentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    incident = tracker.report_incident(vendor_id=vendor_id, **body.model_dump())
    return incident.model_dump()


@router.put("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    incident = tracker.resolve_incident(incident_id)
    if incident is None:
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    return incident.model_dump()


@router.get("/incidents")
async def list_incidents(
    vendor_id: str | None = None,
    active_only: bool = False,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [
        i.model_dump() for i in tracker.list_incidents(vendor_id=vendor_id, active_only=active_only)
    ]


@router.get("/overdue")
async def get_overdue_assessments(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return [v.model_dump() for v in tracker.get_overdue_assessments()]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
