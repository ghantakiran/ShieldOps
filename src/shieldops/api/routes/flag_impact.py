"""Feature flag impact analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.config.flag_impact import (
    FlagCategory,
    ImpactLevel,
    ImpactType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/flag-impact",
    tags=["Flag Impact"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Flag impact service unavailable")
    return _engine


class RecordImpactRequest(BaseModel):
    service_name: str
    flag_category: FlagCategory = FlagCategory.RELEASE
    impact_level: ImpactLevel = ImpactLevel.NONE_DETECTED
    reliability_delta_pct: float = 0.0
    details: str = ""


class AddAnalysisRequest(BaseModel):
    analysis_name: str
    flag_category: FlagCategory = FlagCategory.RELEASE
    impact_type: ImpactType = ImpactType.NEUTRAL
    score: float = 0.0
    description: str = ""


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
    service_name: str | None = None,
    flag_category: FlagCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_impacts(
            service_name=service_name, flag_category=flag_category, limit=limit
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
        raise HTTPException(404, f"Impact record '{record_id}' not found")
    return result.model_dump()


@router.post("/analyses")
async def add_analysis(
    body: AddAnalysisRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_analysis(**body.model_dump())
    return result.model_dump()


@router.get("/service-impact/{service_name}")
async def analyze_flag_impact(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_flag_impact(service_name)


@router.get("/critical-flags")
async def identify_critical_flags(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_flags()


@router.get("/rankings")
async def rank_by_reliability_delta(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_reliability_delta()


@router.get("/trends")
async def detect_impact_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
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


fia_route = router
