"""Incident similarity engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.incident_similarity import (
    MatchConfidence,
    SimilarityDimension,
    SimilarityScope,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/incident-similarity",
    tags=["Incident Similarity"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Incident similarity service unavailable")
    return _engine


class RecordSimilarityRequest(BaseModel):
    service_name: str
    dimension: SimilarityDimension = SimilarityDimension.SYMPTOMS
    confidence: MatchConfidence = MatchConfidence.MODERATE
    scope: SimilarityScope = SimilarityScope.SAME_SERVICE
    match_score: float = 0.0
    details: str = ""


class AddMatchRequest(BaseModel):
    match_name: str
    dimension: SimilarityDimension = SimilarityDimension.SYMPTOMS
    confidence: MatchConfidence = MatchConfidence.MODERATE
    score: float = 0.0
    incident_id: str = ""


@router.post("/similarities")
async def record_similarity(
    body: RecordSimilarityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_similarity(**body.model_dump())
    return result.model_dump()


@router.get("/similarities")
async def list_similarities(
    service_name: str | None = None,
    dimension: SimilarityDimension | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_similarities(
            service_name=service_name, dimension=dimension, limit=limit
        )
    ]


@router.get("/similarities/{record_id}")
async def get_similarity(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_similarity(record_id)
    if result is None:
        raise HTTPException(404, f"Similarity '{record_id}' not found")
    return result.model_dump()


@router.post("/matches")
async def add_match(
    body: AddMatchRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_match(**body.model_dump())
    return result.model_dump()


@router.get("/patterns/{service_name}")
async def analyze_similarity_patterns(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_similarity_patterns(service_name)


@router.get("/high-confidence")
async def identify_high_confidence_matches(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_confidence_matches()


@router.get("/rankings")
async def rank_by_match_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_match_score()


@router.get("/recurring")
async def detect_recurring_similarities(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_recurring_similarities()


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


ism_route = router
