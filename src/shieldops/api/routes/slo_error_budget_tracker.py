"""SLO Error Budget Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_error_budget_tracker import (
    BudgetScope,
    BudgetStatus,
    BurnRate,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-error-budget",
    tags=["SLO Error Budget"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SLO error budget service unavailable")
    return _engine


class RecordBudgetRequest(BaseModel):
    slo_id: str
    budget_status: BudgetStatus = BudgetStatus.UNKNOWN
    budget_scope: BudgetScope = BudgetScope.SERVICE
    burn_rate: BurnRate = BurnRate.NORMAL
    remaining_budget_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAllocationRequest(BaseModel):
    slo_id: str
    budget_status: BudgetStatus = BudgetStatus.UNKNOWN
    allocation_pct: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/budgets")
async def record_budget(
    body: RecordBudgetRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_budget(**body.model_dump())
    return result.model_dump()


@router.get("/budgets")
async def list_budgets(
    status: BudgetStatus | None = None,
    scope: BudgetScope | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_budgets(
            status=status,
            scope=scope,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/budgets/{record_id}")
async def get_budget(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_budget(record_id)
    if result is None:
        raise HTTPException(404, f"Budget record '{record_id}' not found")
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
async def analyze_budget_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_budget_distribution()


@router.get("/exhausted-budgets")
async def identify_exhausted_budgets(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_exhausted_budgets()


@router.get("/remaining-budget-rankings")
async def rank_by_remaining_budget(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_remaining_budget()


@router.get("/trends")
async def detect_budget_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_budget_trends()


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


ebt_route = router
