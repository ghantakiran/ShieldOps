"""Security incident response API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/security-incidents",
    tags=["Security Incidents"],
)

_tracker: Any = None


def set_tracker(tracker: Any) -> None:
    global _tracker
    _tracker = tracker


def _get_tracker() -> Any:
    if _tracker is None:
        raise HTTPException(503, "Security incident service unavailable")
    return _tracker


class CreateIncidentRequest(BaseModel):
    incident_type: str = "unauthorized_access"
    title: str = ""
    description: str = ""
    severity: str = "medium"
    assigned_to: str = ""
    services_affected: list[str] | None = None


class AddActionRequest(BaseModel):
    action: str
    performed_by: str = ""
    outcome: str = "pending"


class CollectEvidenceRequest(BaseModel):
    evidence_type: str = "log_entry"
    description: str = ""
    source: str = ""
    hash_value: str = ""
    collected_by: str = ""


@router.post("/incidents")
async def create_incident(
    body: CreateIncidentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    incident = tracker.create_incident(
        incident_type=body.incident_type,
        title=body.title,
        description=body.description,
        severity=body.severity,
        assigned_to=body.assigned_to,
        services_affected=body.services_affected,
    )
    return incident.model_dump()


@router.get("/incidents")
async def list_incidents(
    incident_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    incidents = tracker.list_incidents(incident_type=incident_type, status=status, limit=limit)
    return [i.model_dump() for i in incidents]


@router.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    incident = tracker.get_incident(incident_id)
    if incident is None:
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    return incident.model_dump()


@router.post("/incidents/{incident_id}/actions")
async def add_containment_action(
    incident_id: str,
    body: AddActionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    action = tracker.add_containment_action(
        incident_id=incident_id,
        action=body.action,
        performed_by=body.performed_by,
        outcome=body.outcome,
    )
    if action is None:
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    return action.model_dump()


@router.post("/incidents/{incident_id}/evidence")
async def collect_evidence(
    incident_id: str,
    body: CollectEvidenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    evidence = tracker.collect_evidence(
        incident_id=incident_id,
        evidence_type=body.evidence_type,
        description=body.description,
        source=body.source,
        hash_value=body.hash_value,
        collected_by=body.collected_by,
    )
    if evidence is None:
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    return evidence.model_dump()


@router.post("/incidents/{incident_id}/escalate")
async def escalate_incident(
    incident_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    if not tracker.escalate_incident(incident_id):
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    return {"escalated": True}


@router.post("/incidents/{incident_id}/close")
async def close_incident(
    incident_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    if not tracker.close_incident(incident_id):
        raise HTTPException(404, f"Incident '{incident_id}' not found")
    return {"closed": True}


@router.get("/incidents/{incident_id}/timeline")
async def get_timeline(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    return tracker.get_timeline(incident_id)


@router.get("/active")
async def get_active_incidents(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    tracker = _get_tracker()
    incidents = tracker.get_active_incidents()
    return [i.model_dump() for i in incidents]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    tracker = _get_tracker()
    return tracker.get_stats()
