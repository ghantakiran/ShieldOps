"""Incident timeline API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.agents.investigation.timeline import TimelineEventType, TimelineStatus
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/incidents", tags=["Incident Timeline"])

_builder: Any = None


def set_builder(builder: Any) -> None:
    global _builder
    _builder = builder


def _get_builder() -> Any:
    if _builder is None:
        raise HTTPException(503, "Timeline service unavailable")
    return _builder


class CreateTimelineRequest(BaseModel):
    affected_services: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddEventRequest(BaseModel):
    event_type: TimelineEventType
    title: str
    description: str = ""
    source: str = ""
    severity: str = "info"
    actor: str = ""
    resource: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    source_type: str  # "investigation" | "remediation" | "alert"
    source_id: str
    title: str
    details: dict[str, Any] = Field(default_factory=dict)


class ResolveRequest(BaseModel):
    root_cause: str
    resolved_by: str = ""


@router.post("/{incident_id}/timeline")
async def create_timeline(
    incident_id: str,
    body: CreateTimelineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    builder = _get_builder()
    tl = builder.create_timeline(incident_id, body.affected_services, body.metadata)
    return tl.model_dump()


@router.get("/{incident_id}/timeline")
async def get_timeline(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    builder = _get_builder()
    tl = builder.get_timeline(incident_id)
    if tl is None:
        raise HTTPException(404, f"Timeline for incident '{incident_id}' not found")
    return tl.model_dump()


@router.post("/{incident_id}/timeline/events")
async def add_timeline_event(
    incident_id: str,
    body: AddEventRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    from shieldops.agents.investigation.timeline import TimelineEvent

    builder = _get_builder()
    event = TimelineEvent(**body.model_dump())
    result = builder.add_event(incident_id, event)
    if result is None:
        raise HTTPException(404, f"Timeline for incident '{incident_id}' not found")
    return result.model_dump()


@router.post("/{incident_id}/timeline/ingest")
async def ingest_timeline_event(
    incident_id: str,
    body: IngestRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    builder = _get_builder()
    if body.source_type == "investigation":
        result = builder.ingest_investigation(
            incident_id,
            body.source_id,
            body.title,
            root_cause=body.details.get("root_cause", ""),
            confidence=body.details.get("confidence", 0.0),
        )
    elif body.source_type == "remediation":
        result = builder.ingest_remediation(
            incident_id,
            body.source_id,
            body.title,
            status=body.details.get("status", ""),
        )
    elif body.source_type == "alert":
        result = builder.ingest_alert(
            incident_id,
            body.source_id,
            body.title,
            severity=body.details.get("severity", "warning"),
            source=body.details.get("source", ""),
        )
    else:
        raise HTTPException(400, f"Unknown source type: {body.source_type}")
    if result is None:
        raise HTTPException(404, f"Timeline for incident '{incident_id}' not found")
    return result.model_dump()


@router.put("/{incident_id}/timeline/resolve")
async def resolve_timeline(
    incident_id: str,
    body: ResolveRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    builder = _get_builder()
    tl = builder.resolve_timeline(incident_id, body.root_cause, body.resolved_by)
    if tl is None:
        raise HTTPException(404, f"Timeline for incident '{incident_id}' not found")
    return tl.model_dump()


@router.get("/timelines")
async def list_timelines(
    status: TimelineStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    builder = _get_builder()
    return [t.model_dump() for t in builder.list_timelines(status=status, limit=limit)]
