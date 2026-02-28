"""Postmortem quality scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.postmortem_quality import (
    QualityDimension,
    QualityGrade,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/postmortem-quality",
    tags=["Postmortem Quality"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Postmortem quality service unavailable")
    return _engine


class RecordPostmortemRequest(BaseModel):
    service_name: str
    dimension: QualityDimension = QualityDimension.TIMELINE_ACCURACY
    grade: QualityGrade = QualityGrade.ADEQUATE
    quality_score: float = 0.0
    details: str = ""


class AddDimensionScoreRequest(BaseModel):
    dimension_name: str
    dimension: QualityDimension = QualityDimension.TIMELINE_ACCURACY
    grade: QualityGrade = QualityGrade.ADEQUATE
    score: float = 0.0
    description: str = ""


@router.post("/postmortems")
async def record_postmortem(
    body: RecordPostmortemRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_postmortem(**body.model_dump())
    return result.model_dump()


@router.get("/postmortems")
async def list_postmortems(
    service_name: str | None = None,
    dimension: QualityDimension | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_postmortems(
            service_name=service_name, dimension=dimension, limit=limit
        )
    ]


@router.get("/postmortems/{record_id}")
async def get_postmortem(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_postmortem(record_id)
    if result is None:
        raise HTTPException(404, f"Postmortem record '{record_id}' not found")
    return result.model_dump()


@router.post("/dimension-scores")
async def add_dimension_score(
    body: AddDimensionScoreRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_dimension_score(**body.model_dump())
    return result.model_dump()


@router.get("/service-quality/{service_name}")
async def analyze_postmortem_quality(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_postmortem_quality(service_name)


@router.get("/poor-postmortems")
async def identify_poor_postmortems(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_poor_postmortems()


@router.get("/rankings")
async def rank_by_quality_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_quality_score()


@router.get("/trends")
async def detect_quality_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_quality_trends()


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


pmq_route = router
