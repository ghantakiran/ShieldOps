"""Alert Noise Profiler API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.alert_noise_profiler import (
    NoiseCategory,
    NoiseImpact,
    NoiseSource,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/alert-noise-profiler",
    tags=["Alert Noise Profiler"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Alert noise profiler service unavailable")
    return _engine


class RecordProfileRequest(BaseModel):
    profile_id: str
    noise_category: NoiseCategory = NoiseCategory.ACTIONABLE
    noise_source: NoiseSource = NoiseSource.LEGITIMATE
    noise_impact: NoiseImpact = NoiseImpact.NEGLIGIBLE
    noise_ratio: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    profile_id: str
    noise_category: NoiseCategory = NoiseCategory.ACTIONABLE
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/profiles")
async def record_profile(
    body: RecordProfileRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_profile(**body.model_dump())
    return result.model_dump()


@router.get("/profiles")
async def list_profiles(
    noise_category: NoiseCategory | None = None,
    noise_source: NoiseSource | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_profiles(
            noise_category=noise_category,
            noise_source=noise_source,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/profiles/{record_id}")
async def get_profile(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_profile(record_id)
    if result is None:
        raise HTTPException(404, f"Profile '{record_id}' not found")
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
async def analyze_noise_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_noise_distribution()


@router.get("/high-noise")
async def identify_high_noise(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_noise()


@router.get("/noise-rankings")
async def rank_by_noise_ratio(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_noise_ratio()


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


anf_route = router
