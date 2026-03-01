"""Incident Noise Filter API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.noise_filter import (
    FilterAction,
    NoiseCategory,
    NoiseConfidence,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/noise-filter", tags=["Noise Filter"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Noise filter service unavailable")
    return _engine


class RecordNoiseRequest(BaseModel):
    incident_id: str
    noise_category: NoiseCategory = NoiseCategory.FALSE_ALARM
    confidence: NoiseConfidence = NoiseConfidence.UNCLASSIFIED
    filter_action: FilterAction = FilterAction.PASS_THROUGH
    team: str = ""
    details: str = ""
    model_config = {"extra": "forbid"}


class AddPatternRequest(BaseModel):
    pattern_name: str
    noise_category: NoiseCategory = NoiseCategory.FALSE_ALARM
    occurrence_count: int = 0
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_noise(
    body: RecordNoiseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_noise(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_noise(
    category: NoiseCategory | None = None,
    confidence: NoiseConfidence | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_noise(
            category=category,
            confidence=confidence,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_noise(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_noise(record_id)
    if result is None:
        raise HTTPException(404, f"Noise record '{record_id}' not found")
    return result.model_dump()


@router.post("/patterns")
async def add_pattern(
    body: AddPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_pattern(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_noise_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_noise_distribution()


@router.get("/false-alarms")
async def identify_false_alarms(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_false_alarms()


@router.get("/volume-rankings")
async def rank_by_noise_volume(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_noise_volume()


@router.get("/trends")
async def detect_noise_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_noise_trends()


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


inf_route = router
