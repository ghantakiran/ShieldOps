"""Team Expertise Mapper API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.expertise_mapper import (
    ExpertiseArea,
    ExpertiseGap,
    ExpertiseLevel,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/expertise-mapper", tags=["Expertise Mapper"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Expertise mapper service unavailable")
    return _engine


class RecordExpertiseRequest(BaseModel):
    team_member: str
    expertise_area: ExpertiseArea = ExpertiseArea.INFRASTRUCTURE
    expertise_level: ExpertiseLevel = ExpertiseLevel.NONE
    expertise_gap: ExpertiseGap = ExpertiseGap.CRITICAL_GAP
    coverage_pct: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    assessment_name: str
    expertise_area: ExpertiseArea = ExpertiseArea.INFRASTRUCTURE
    skill_score: float = 0.0
    assessed_members: int = 0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_expertise(
    body: RecordExpertiseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_expertise(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_expertise(
    expertise_area: ExpertiseArea | None = None,
    expertise_level: ExpertiseLevel | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_expertise(
            expertise_area=expertise_area,
            expertise_level=expertise_level,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_expertise(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_expertise(record_id)
    if result is None:
        raise HTTPException(404, f"Expertise record '{record_id}' not found")
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
async def analyze_expertise_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_expertise_distribution()


@router.get("/expertise-gaps")
async def identify_expertise_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_expertise_gaps()


@router.get("/coverage-rankings")
async def rank_by_coverage_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_coverage_score()


@router.get("/trends")
async def detect_expertise_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_expertise_trends()


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


tem_route = router
