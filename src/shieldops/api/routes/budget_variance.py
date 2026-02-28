"""Budget variance tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.budget_variance import (
    BudgetCategory,
    VarianceSeverity,
    VarianceType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/budget-variance",
    tags=["Budget Variance"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Budget variance tracker service unavailable")
    return _engine


class RecordVarianceRequest(BaseModel):
    budget_name: str
    category: BudgetCategory = BudgetCategory.INFRASTRUCTURE
    variance_type: VarianceType | None = None
    severity: VarianceSeverity | None = None
    budgeted_amount: float = 0.0
    actual_amount: float = 0.0
    variance_pct: float = 0.0
    period: str = ""
    details: str = ""


class AddDetailRequest(BaseModel):
    budget_name: str
    category: BudgetCategory = BudgetCategory.INFRASTRUCTURE
    line_item: str = ""
    variance_amount: float = 0.0
    reason: str = ""


@router.post("/variances")
async def record_variance(
    body: RecordVarianceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_variance(**body.model_dump())
    return result.model_dump()


@router.get("/variances")
async def list_variances(
    budget_name: str | None = None,
    category: BudgetCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_variances(
            budget_name=budget_name,
            category=category,
            limit=limit,
        )
    ]


@router.get("/variances/{record_id}")
async def get_variance(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_variance(record_id)
    if result is None:
        raise HTTPException(404, f"Variance record '{record_id}' not found")
    return result.model_dump()


@router.post("/details")
async def add_detail(
    body: AddDetailRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_detail(**body.model_dump())
    return result.model_dump()


@router.get("/category/{category}")
async def analyze_variance_by_category(
    category: BudgetCategory,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_variance_by_category(category)


@router.get("/over-budget")
async def identify_over_budget_items(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_over_budget_items()


@router.get("/rankings")
async def rank_by_variance_pct(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_variance_pct()


@router.get("/trends")
async def detect_variance_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_variance_trends()


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


bvt_route = router
