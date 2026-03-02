"""Stakeholder Impact Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.stakeholder_impact_tracker import (
    CommunicationChannel,
    ImpactLevel,
    StakeholderGroup,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/stakeholder-impact-tracker",
    tags=["Stakeholder Impact Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Stakeholder impact tracker service unavailable")
    return _engine


class RecordImpactRequest(BaseModel):
    incident_id: str
    stakeholder_group: StakeholderGroup = StakeholderGroup.EXECUTIVE
    impact_level: ImpactLevel = ImpactLevel.CRITICAL
    communication_channel: CommunicationChannel = CommunicationChannel.EMAIL
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    incident_id: str
    stakeholder_group: StakeholderGroup = StakeholderGroup.EXECUTIVE
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/impacts")
async def record_impact(
    body: RecordImpactRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_impact(**body.model_dump())
    return result.model_dump()


@router.get("/impacts")
async def list_impacts(
    stakeholder_group: StakeholderGroup | None = None,
    impact_level: ImpactLevel | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_impacts(
            stakeholder_group=stakeholder_group,
            impact_level=impact_level,
            team=team,
            limit=limit,
        )
    ]


@router.get("/impacts/{record_id}")
async def get_impact(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_impact(record_id)
    if result is None:
        raise HTTPException(404, f"Impact '{record_id}' not found")
    return result.model_dump()


@router.post("/assessments")
async def add_assessment(
    body: AddAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_impact_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_impact_distribution()


@router.get("/high-impact-stakeholders")
async def identify_high_impact_stakeholders(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_impact_stakeholders()


@router.get("/impact-rankings")
async def rank_by_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact()


@router.get("/trends")
async def detect_impact_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_impact_trends()


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


sit_route = router
