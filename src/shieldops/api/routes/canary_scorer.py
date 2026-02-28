"""Deployment canary scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.canary_scorer import (
    CanaryMetric,
    CanaryStage,
    CanaryVerdict,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/canary-scorer",
    tags=["Canary Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Canary scorer service unavailable",
        )
    return _engine


class RecordCanaryRequest(BaseModel):
    model_config = {"extra": "forbid"}

    deployment_id: str
    service: str
    stage: CanaryStage = CanaryStage.BASELINE
    canary_score: float = 0.0
    verdict: CanaryVerdict = CanaryVerdict.INCONCLUSIVE
    team: str = ""
    duration_minutes: float = 0.0
    details: str = ""


class AddComparisonRequest(BaseModel):
    model_config = {"extra": "forbid"}

    deployment_id: str
    metric: CanaryMetric = CanaryMetric.ERROR_RATE
    baseline_value: float = 0.0
    canary_value: float = 0.0
    deviation_pct: float = 0.0


@router.post("/canaries")
async def record_canary(
    body: RecordCanaryRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_canary(**body.model_dump())
    return result.model_dump()


@router.get("/canaries")
async def list_canaries(
    verdict: CanaryVerdict | None = None,
    stage: CanaryStage | None = None,
    service: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_canaries(
            verdict=verdict,
            stage=stage,
            service=service,
            limit=limit,
        )
    ]


@router.get("/canaries/{record_id}")
async def get_canary(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_canary(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Canary '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/comparisons")
async def add_comparison(
    body: AddComparisonRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_comparison(**body.model_dump())
    return result.model_dump()


@router.get("/success-rate")
async def analyze_canary_success_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_canary_success_rate()


@router.get("/failed")
async def identify_failed_canaries(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failed_canaries()


@router.get("/rankings")
async def rank_by_canary_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_canary_score()


@router.get("/trends")
async def detect_canary_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_canary_trends()


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


dcs_route = router
