"""Incident timeline reconstructor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/timeline-reconstructor", tags=["Timeline Reconstructor"])

_reconstructor: Any = None


def set_reconstructor(reconstructor: Any) -> None:
    global _reconstructor
    _reconstructor = reconstructor


def _get_reconstructor() -> Any:
    if _reconstructor is None:
        raise HTTPException(503, "Timeline reconstructor service unavailable")
    return _reconstructor


class RecordEventRequest(BaseModel):
    incident_id: str
    source: str = "LOG"
    phase: str = "PRE_INCIDENT"
    timestamp: float = 0.0
    description: str = ""
    service_name: str = ""
    correlation_confidence: str = "MEDIUM"


@router.post("/events")
async def record_event(
    body: RecordEventRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconstructor = _get_reconstructor()
    event = reconstructor.record_event(**body.model_dump())
    return event.model_dump()


@router.get("/events")
async def list_events(
    incident_id: str | None = None,
    source: str | None = None,
    phase: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reconstructor = _get_reconstructor()
    return [
        e.model_dump()
        for e in reconstructor.list_events(
            incident_id=incident_id, source=source, phase=phase, limit=limit
        )
    ]


@router.get("/events/{event_id}")
async def get_event(
    event_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconstructor = _get_reconstructor()
    event = reconstructor.get_event(event_id)
    if event is None:
        raise HTTPException(404, f"Event '{event_id}' not found")
    return event.model_dump()


@router.post("/reconstruct/{incident_id}")
async def reconstruct_timeline(
    incident_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconstructor = _get_reconstructor()
    timeline = reconstructor.reconstruct_timeline(incident_id)
    return timeline.model_dump()


@router.get("/root-causes/{incident_id}")
async def identify_root_cause_candidates(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[str]:
    reconstructor = _get_reconstructor()
    return reconstructor.identify_root_cause_candidates(incident_id)


@router.get("/detection-delay/{incident_id}")
async def calculate_detection_delay(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconstructor = _get_reconstructor()
    delay = reconstructor.calculate_detection_delay(incident_id)
    return {"incident_id": incident_id, "detection_delay_seconds": delay}


@router.get("/phase-transitions/{incident_id}")
async def analyze_phase_transitions(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reconstructor = _get_reconstructor()
    return reconstructor.analyze_phase_transitions(incident_id)


@router.get("/correlated/{event_id}")
async def find_correlated_events(
    event_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    reconstructor = _get_reconstructor()
    return [e.model_dump() for e in reconstructor.find_correlated_events(event_id)]


@router.get("/analysis-report")
async def generate_analysis_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconstructor = _get_reconstructor()
    return reconstructor.generate_analysis_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    reconstructor = _get_reconstructor()
    return reconstructor.get_stats()
