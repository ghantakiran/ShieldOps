"""Deploy Canary Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.deploy_canary_analyzer import (
    CanaryOutcome,
    CanarySignal,
    CanaryStrategy,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/deploy-canary-analyzer",
    tags=["Deploy Canary Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Deploy canary analyzer service unavailable")
    return _engine


class RecordCanaryRequest(BaseModel):
    canary_id: str
    canary_outcome: CanaryOutcome = CanaryOutcome.INCONCLUSIVE
    canary_signal: CanarySignal = CanarySignal.HEALTHY
    canary_strategy: CanaryStrategy = CanaryStrategy.PERCENTAGE
    success_rate: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    canary_id: str
    canary_outcome: CanaryOutcome = CanaryOutcome.INCONCLUSIVE
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


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
    canary_outcome: CanaryOutcome | None = None,
    canary_signal: CanarySignal | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_canaries(
            canary_outcome=canary_outcome,
            canary_signal=canary_signal,
            team=team,
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
        raise HTTPException(404, f"Canary '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_canary_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_canary_distribution()


@router.get("/failed-canaries")
async def identify_failed_canaries(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failed_canaries()


@router.get("/success-rate-rankings")
async def rank_by_success_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_success_rate()


@router.get("/trends")
async def detect_canary_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
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


dcx_route = router
