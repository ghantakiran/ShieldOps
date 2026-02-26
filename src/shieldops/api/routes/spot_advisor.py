"""Spot instance advisor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.spot_advisor import (
    InterruptionRisk,
    SavingsGrade,
    SpotMarket,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/spot-advisor",
    tags=["Spot Advisor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Spot advisor service unavailable")
    return _engine


class RecordUsageRequest(BaseModel):
    instance_type: str
    market: SpotMarket = SpotMarket.ON_DEMAND
    interruption_risk: InterruptionRisk = InterruptionRisk.MODERATE
    savings_pct: float = 0.0
    monthly_cost: float = 0.0
    on_demand_cost: float = 0.0
    details: str = ""


class AddRecommendationRequest(BaseModel):
    instance_type: str
    recommended_market: SpotMarket = SpotMarket.AWS_SPOT
    savings_grade: SavingsGrade | None = None
    estimated_savings_pct: float = 0.0
    reason: str = ""


@router.post("/usage")
async def record_usage(
    body: RecordUsageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_usage(**body.model_dump())
    return result.model_dump()


@router.get("/usage")
async def list_usage(
    instance_type: str | None = None,
    market: SpotMarket | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_usage(
            instance_type=instance_type,
            market=market,
            limit=limit,
        )
    ]


@router.get("/usage/{record_id}")
async def get_usage(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_usage(record_id)
    if result is None:
        raise HTTPException(404, f"Usage record '{record_id}' not found")
    return result.model_dump()


@router.post("/recommendations")
async def add_recommendation(
    body: AddRecommendationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_recommendation(**body.model_dump())
    return result.model_dump()


@router.get("/suitability/{instance_type}")
async def analyze_spot_suitability(
    instance_type: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_spot_suitability(instance_type)


@router.get("/high-savings")
async def identify_high_savings_opportunities(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_savings_opportunities()


@router.get("/rankings")
async def rank_by_interruption_risk(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_interruption_risk()


@router.get("/total-savings")
async def estimate_total_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.estimate_total_savings()


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


spa_route = router
