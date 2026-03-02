"""Operational Hygiene Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.operational_hygiene_scorer import (
    HygieneDimension,
    HygieneGrade,
    RemediationPriority,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/operational-hygiene-scorer",
    tags=["Operational Hygiene Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Operational hygiene scorer service unavailable")
    return _engine


class RecordHygieneRequest(BaseModel):
    service_name: str
    hygiene_dimension: HygieneDimension = HygieneDimension.RUNBOOK_FRESHNESS
    hygiene_grade: HygieneGrade = HygieneGrade.EXCELLENT
    remediation_priority: RemediationPriority = RemediationPriority.IMMEDIATE
    hygiene_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    service_name: str
    hygiene_dimension: HygieneDimension = HygieneDimension.RUNBOOK_FRESHNESS
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/hygiene-records")
async def record_hygiene(
    body: RecordHygieneRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_hygiene(**body.model_dump())
    return result.model_dump()


@router.get("/hygiene-records")
async def list_hygiene_records(
    hygiene_dimension: HygieneDimension | None = None,
    hygiene_grade: HygieneGrade | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_hygiene_records(
            hygiene_dimension=hygiene_dimension,
            hygiene_grade=hygiene_grade,
            team=team,
            limit=limit,
        )
    ]


@router.get("/hygiene-records/{record_id}")
async def get_hygiene(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    found = engine.get_hygiene(record_id)
    if found is None:
        raise HTTPException(404, f"Hygiene record '{record_id}' not found")
    return found.model_dump()


@router.post("/assessments")
async def add_assessment(
    body: AddAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_hygiene_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_hygiene_distribution()


@router.get("/poor-hygiene")
async def identify_poor_hygiene(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_poor_hygiene()


@router.get("/hygiene-rankings")
async def rank_by_hygiene(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_hygiene()


@router.get("/trends")
async def detect_hygiene_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_hygiene_trends()


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


ohs_route = router
