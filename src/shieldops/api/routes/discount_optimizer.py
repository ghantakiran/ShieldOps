"""Cloud discount optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.discount_optimizer import (
    CloudProvider,
    DiscountType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/discount-optimizer",
    tags=["Discount Optimizer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Discount optimizer service unavailable",
        )
    return _engine


class RecordDiscountRequest(BaseModel):
    name: str
    discount_type: DiscountType
    provider: CloudProvider = CloudProvider.AWS
    monthly_spend: float = 0.0
    monthly_savings: float = 0.0
    coverage_pct: float = 0.0
    expiry_days: int = 365


@router.post("/discounts")
async def record_discount(
    body: RecordDiscountRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_discount(**body.model_dump())
    return result.model_dump()


@router.get("/discounts")
async def list_discounts(
    provider: CloudProvider | None = None,
    discount_type: DiscountType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_discounts(provider=provider, discount_type=discount_type, limit=limit)
    ]


@router.get("/discounts/{record_id}")
async def get_discount(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_discount(record_id)
    if result is None:
        raise HTTPException(404, f"Discount '{record_id}' not found")
    return result.model_dump()


@router.post("/strategy")
async def generate_strategy(
    provider: CloudProvider = CloudProvider.AWS,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_strategy(provider).model_dump()


@router.get("/coverage-gaps")
async def calculate_coverage_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.calculate_coverage_gaps()


@router.get("/expiring")
async def identify_expiring_discounts(
    within_days: int = 60,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_expiring_discounts(within_days)


@router.get("/portfolio-mix")
async def optimize_portfolio_mix(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.optimize_portfolio_mix()


@router.get("/savings-potential")
async def estimate_savings_potential(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.estimate_savings_potential()


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


do_route = router
