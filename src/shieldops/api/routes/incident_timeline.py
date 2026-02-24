"""Incident timeline API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/incident-timeline",
    tags=["Incident Timeline"],
)

_analyzer: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _analyzer
    _analyzer = analyzer


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(
            503,
            "Incident timeline service unavailable",
        )
    return _analyzer


# -- Request models -------------------------------------------------


class RecordPhaseRequest(BaseModel):
    incident_id: str
    phase: str = "detection"
    started_at: float | None = None
    ended_at: float = 0.0
    duration_minutes: float = 0.0
    assignee: str = ""
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompareRequest(BaseModel):
    incident_ids: list[str] = Field(default_factory=list)


# -- Routes ---------------------------------------------------------


@router.post("/entries")
async def record_phase(
    body: RecordPhaseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    entry = analyzer.record_phase(**body.model_dump())
    return entry.model_dump()


@router.get("/entries/{entry_id}")
async def get_entry(
    entry_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    entry = analyzer.get_entry(entry_id)
    if entry is None:
        raise HTTPException(
            404,
            f"Entry '{entry_id}' not found",
        )
    return entry.model_dump()


@router.get("/entries")
async def list_entries(
    incident_id: str | None = None,
    phase: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    items = analyzer.list_entries(
        incident_id=incident_id,
        phase=phase,
        limit=limit,
    )
    return [e.model_dump() for e in items]


@router.get("/durations/{incident_id}")
async def calculate_phase_durations(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, float]:
    analyzer = _get_analyzer()
    return analyzer.calculate_phase_durations(incident_id)


@router.get("/bottlenecks/{incident_id}")
async def detect_bottlenecks(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    bns = analyzer.detect_bottlenecks(incident_id)
    return [b.model_dump() for b in bns]


@router.get("/quality/{incident_id}")
async def analyze_response_quality(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, str]:
    analyzer = _get_analyzer()
    quality = analyzer.analyze_response_quality(incident_id)
    return {"incident_id": incident_id, "quality": quality}


@router.post("/compare")
async def compare_timelines(
    body: CompareRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.compare_incident_timelines(
        body.incident_ids,
    )


@router.get("/improvements")
async def identify_improvements(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.identify_improvement_areas()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.generate_timeline_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
