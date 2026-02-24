"""FinOps maturity API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/finops-maturity", tags=["FinOps Maturity"])

_scorer: Any = None


def set_scorer(scorer: Any) -> None:
    global _scorer
    _scorer = scorer


def _get_scorer() -> Any:
    if _scorer is None:
        raise HTTPException(503, "FinOps maturity service unavailable")
    return _scorer


class CreateAssessmentRequest(BaseModel):
    organization: str
    assessor: str
    notes: str = ""


class ScoreDimensionRequest(BaseModel):
    dimension: str
    area: str
    score: float
    findings: str | None = None


@router.post("/assessments")
async def create_assessment(
    body: CreateAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    assessment = scorer.create_assessment(**body.model_dump())
    return assessment.model_dump()


@router.get("/assessments")
async def list_assessments(
    organization: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [a.model_dump() for a in scorer.list_assessments(organization=organization, limit=limit)]


@router.get("/assessments/{assessment_id}")
async def get_assessment(
    assessment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    assessment = scorer.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(404, f"Assessment '{assessment_id}' not found")
    return assessment.model_dump()


@router.post("/assessments/{assessment_id}/dimensions")
async def score_dimension(
    assessment_id: str,
    body: ScoreDimensionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    result = scorer.score_dimension(assessment_id, **body.model_dump())
    if result is None:
        raise HTTPException(404, f"Assessment '{assessment_id}' not found")
    return result.model_dump()


@router.post("/assessments/{assessment_id}/maturity")
async def calculate_overall_maturity(
    assessment_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    result = scorer.calculate_overall_maturity(assessment_id)
    return result.model_dump()


@router.get("/assessments/{assessment_id}/improvements")
async def identify_improvement_areas(
    assessment_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [i.model_dump() for i in scorer.identify_improvement_areas(assessment_id)]


@router.get("/trend/{organization}")
async def track_maturity_trend(
    organization: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [t.model_dump() for t in scorer.track_maturity_trend(organization)]


@router.post("/assessments/{assessment_id}/benchmarks")
async def compare_with_benchmarks(
    assessment_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    result = scorer.compare_with_benchmarks(assessment_id)
    return result.model_dump()


@router.get("/report")
async def generate_maturity_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    return scorer.generate_maturity_report()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    return scorer.get_stats()
