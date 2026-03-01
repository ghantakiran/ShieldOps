"""Feature Flag Impact Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.feature_flag_impact import (
    FlagImpactType,
    FlagRisk,
    FlagStatus,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/feature-flag-impact", tags=["Feature Flag Impact"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Feature flag impact service unavailable")
    return _engine


class RecordImpactRequest(BaseModel):
    flag_id: str
    flag_impact_type: FlagImpactType = FlagImpactType.PERFORMANCE
    flag_status: FlagStatus = FlagStatus.ACTIVE
    flag_risk: FlagRisk = FlagRisk.LOW
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMeasurementRequest(BaseModel):
    flag_id: str
    flag_impact_type: FlagImpactType = FlagImpactType.PERFORMANCE
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_impact(
    body: RecordImpactRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_impact(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_impacts(
    impact_type: FlagImpactType | None = None,
    status: FlagStatus | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_impacts(
            impact_type=impact_type,
            status=status,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_impact(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_impact(record_id)
    if result is None:
        raise HTTPException(404, f"Impact record '{record_id}' not found")
    return result.model_dump()


@router.post("/measurements")
async def add_measurement(
    body: AddMeasurementRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_measurement(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_flag_performance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_flag_performance()


@router.get("/negative-flags")
async def identify_negative_flags(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_negative_flags()


@router.get("/score-rankings")
async def rank_by_impact_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact_score()


@router.get("/regressions")
async def detect_impact_regressions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_impact_regressions()


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


ffi_route = router
