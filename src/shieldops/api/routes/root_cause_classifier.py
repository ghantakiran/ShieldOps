"""Incident root cause classifier API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.root_cause_classifier import (
    ClassificationConfidence,
    ClassificationMethod,
    RootCauseCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/root-cause-classifier",
    tags=["Root Cause Classifier"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Root cause classifier service unavailable",
        )
    return _engine


class RecordClassificationRequest(BaseModel):
    model_config = {"extra": "forbid"}

    incident_id: str
    category: RootCauseCategory = RootCauseCategory.CODE_DEFECT
    confidence: ClassificationConfidence = ClassificationConfidence.MODERATE
    method: ClassificationMethod = ClassificationMethod.AUTOMATED
    root_cause_description: str = ""
    service: str = ""
    team: str = ""


class AddCausePatternRequest(BaseModel):
    model_config = {"extra": "forbid"}

    category: RootCauseCategory = RootCauseCategory.CODE_DEFECT
    pattern_name: str = ""
    occurrence_count: int = 0
    avg_resolution_minutes: float = 0.0


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
    category: RootCauseCategory | None = None,
    confidence: (ClassificationConfidence | None) = None,
    service: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_classifications(
            category=category,
            confidence=confidence,
            service=service,
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
        raise HTTPException(
            404,
            f"Classification '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/patterns")
async def add_cause_pattern(
    body: AddCausePatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_cause_pattern(**body.model_dump())
    return result.model_dump()


@router.get("/by-category")
async def analyze_causes_by_category(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_causes_by_category()


@router.get("/low-confidence")
async def identify_low_confidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_confidence_classifications()


@router.get("/rankings")
async def rank_by_occurrence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_occurrence()


@router.get("/trends")
async def detect_classification_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_classification_trends()


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


rcc_route = router
