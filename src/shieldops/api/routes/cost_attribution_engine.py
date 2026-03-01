"""Cost Attribution Engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.cost_attribution_engine import (
    AttributionAccuracy,
    AttributionMethod,
    CostCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cost-attribution",
    tags=["Cost Attribution"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cost attribution service unavailable")
    return _engine


class RecordAttributionRequest(BaseModel):
    attribution_id: str
    attribution_method: AttributionMethod = AttributionMethod.DIRECT
    cost_category: CostCategory = CostCategory.INFRASTRUCTURE
    attribution_accuracy: AttributionAccuracy = AttributionAccuracy.UNKNOWN
    cost_amount: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddDetailRequest(BaseModel):
    attribution_id: str
    attribution_method: AttributionMethod = AttributionMethod.DIRECT
    detail_amount: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/attributions")
async def record_attribution(
    body: RecordAttributionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_attribution(**body.model_dump())
    return result.model_dump()


@router.get("/attributions")
async def list_attributions(
    method: AttributionMethod | None = None,
    category: CostCategory | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_attributions(
            method=method,
            category=category,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/attributions/{record_id}")
async def get_attribution(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_attribution(record_id)
    if result is None:
        raise HTTPException(404, f"Attribution record '{record_id}' not found")
    return result.model_dump()


@router.post("/details")
async def add_detail(
    body: AddDetailRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_detail(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_attribution_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_attribution_distribution()


@router.get("/disputed-attributions")
async def identify_disputed_attributions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_disputed_attributions()


@router.get("/cost-rankings")
async def rank_by_cost_amount(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_cost_amount()


@router.get("/trends")
async def detect_attribution_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_attribution_trends()


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


cae_route = router
