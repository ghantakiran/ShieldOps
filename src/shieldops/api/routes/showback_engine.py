"""Showback Engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.showback_engine import (
    ShowbackAccuracy,
    ShowbackCategory,
    ShowbackGranularity,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/showback-engine", tags=["Showback Engine"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Showback engine service unavailable")
    return _engine


class RecordShowbackRequest(BaseModel):
    consumer_id: str
    showback_category: ShowbackCategory = ShowbackCategory.COMPUTE
    showback_granularity: ShowbackGranularity = ShowbackGranularity.MONTHLY
    showback_accuracy: ShowbackAccuracy = ShowbackAccuracy.UNKNOWN
    cost_amount: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAllocationRequest(BaseModel):
    consumer_id: str
    showback_category: ShowbackCategory = ShowbackCategory.COMPUTE
    allocation_amount: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_showback(
    body: RecordShowbackRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_showback(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_showbacks(
    category: ShowbackCategory | None = None,
    granularity: ShowbackGranularity | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_showbacks(
            category=category,
            granularity=granularity,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_showback(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_showback(record_id)
    if result is None:
        raise HTTPException(404, f"Showback record '{record_id}' not found")
    return result.model_dump()


@router.post("/allocations")
async def add_allocation(
    body: AddAllocationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_allocation(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_cost_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_cost_distribution()


@router.get("/over-budget")
async def identify_over_budget_consumers(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_over_budget_consumers()


@router.get("/cost-rankings")
async def rank_by_cost_amount(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_cost_amount()


@router.get("/trends")
async def detect_cost_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_cost_trends()


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


sbe_route = router
