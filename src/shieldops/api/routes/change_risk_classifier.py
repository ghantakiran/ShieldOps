"""Change Risk Classifier API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.change_risk_classifier import (
    ClassificationMethod,
    RiskFactor,
    RiskLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/change-risk-classifier",
    tags=["Change Risk Classifier"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Change risk classifier service unavailable")
    return _engine


class RecordClassificationRequest(BaseModel):
    classification_id: str
    risk_level: RiskLevel = RiskLevel.MODERATE
    risk_factor: RiskFactor = RiskFactor.BLAST_RADIUS
    classification_method: ClassificationMethod = ClassificationMethod.RULE_BASED
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    classification_id: str
    risk_level: RiskLevel = RiskLevel.MODERATE
    assessment_score: float = 0.0
    threshold: float = 15.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/classifications")
async def record_classification(
    body: RecordClassificationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_classification(**body.model_dump())
    return result.model_dump()


@router.get("/classifications")
async def list_classifications(
    risk_level: RiskLevel | None = None,
    risk_factor: RiskFactor | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_classifications(
            risk_level=risk_level,
            risk_factor=risk_factor,
            team=team,
            limit=limit,
        )
    ]


@router.get("/classifications/{record_id}")
async def get_classification(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_classification(record_id)
    if result is None:
        raise HTTPException(404, f"Classification '{record_id}' not found")
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
async def analyze_risk_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_risk_distribution()


@router.get("/high-risk-changes")
async def identify_high_risk_changes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_changes()


@router.get("/risk-rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/trends")
async def detect_risk_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_risk_trends()


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


crc_route = router
