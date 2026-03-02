"""Incident Mitigation Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.incident_mitigation_tracker import (
    MitigationCategory,
    MitigationStatus,
    MitigationUrgency,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/incident-mitigation-tracker",
    tags=["Incident Mitigation Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Incident mitigation tracker service unavailable")
    return _engine


class RecordMitigationRequest(BaseModel):
    incident_id: str
    mitigation_status: MitigationStatus = MitigationStatus.PENDING
    mitigation_category: MitigationCategory = MitigationCategory.INFRASTRUCTURE
    mitigation_urgency: MitigationUrgency = MitigationUrgency.CRITICAL
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAnalysisRequest(BaseModel):
    incident_id: str
    mitigation_status: MitigationStatus = MitigationStatus.PENDING
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/mitigations")
async def record_mitigation(
    body: RecordMitigationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_mitigation(**body.model_dump())
    return result.model_dump()


@router.get("/mitigations")
async def list_mitigations(
    mitigation_status: MitigationStatus | None = None,
    mitigation_category: MitigationCategory | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_mitigations(
            mitigation_status=mitigation_status,
            mitigation_category=mitigation_category,
            team=team,
            limit=limit,
        )
    ]


@router.get("/mitigations/{record_id}")
async def get_mitigation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_mitigation(record_id)
    if result is None:
        raise HTTPException(404, f"Mitigation '{record_id}' not found")
    return result.model_dump()


@router.post("/analyses")
async def add_analysis(
    body: AddAnalysisRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_analysis(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_mitigation_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_mitigation_distribution()


@router.get("/low-effectiveness")
async def identify_low_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_effectiveness()


@router.get("/effectiveness-rankings")
async def rank_by_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_effectiveness()


@router.get("/trends")
async def detect_mitigation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_mitigation_trends()


@router.get("/report")
async def generate_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    engine = _get_engine()
    return engine.clear_data()


imt_route = router
