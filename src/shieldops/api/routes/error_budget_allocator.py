"""Error budget allocator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.error_budget_allocator import (
    AllocationStrategy,
    BudgetStatus,
    ConsumptionRate,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/error-budget-allocator",
    tags=["Error Budget Allocator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Error budget allocator unavailable",
        )
    return _engine


class RecordAllocationRequest(BaseModel):
    service_name: str
    strategy: AllocationStrategy = AllocationStrategy.PROPORTIONAL
    status: BudgetStatus = BudgetStatus.HEALTHY
    consumption: ConsumptionRate = ConsumptionRate.NORMAL
    budget_pct: float = 0.0
    details: str = ""


class AddPolicyRequest(BaseModel):
    policy_name: str
    strategy: AllocationStrategy = AllocationStrategy.PROPORTIONAL
    status: BudgetStatus = BudgetStatus.HEALTHY
    freeze_threshold_pct: float = 5.0
    alert_threshold_pct: float = 20.0


@router.post("/allocations")
async def record_allocation(
    body: RecordAllocationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_allocation(**body.model_dump())
    return result.model_dump()


@router.get("/allocations")
async def list_allocations(
    service_name: str | None = None,
    strategy: AllocationStrategy | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_allocations(
            service_name=service_name,
            strategy=strategy,
            limit=limit,
        )
    ]


@router.get("/allocations/{record_id}")
async def get_allocation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_allocation(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Allocation '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/policies")
async def add_policy(
    body: AddPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_policy(**body.model_dump())
    return result.model_dump()


@router.get("/health/{service_name}")
async def analyze_budget_health(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_budget_health(service_name)


@router.get("/exhausted-budgets")
async def identify_exhausted_budgets(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_exhausted_budgets()


@router.get("/rankings")
async def rank_by_budget_usage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_budget_usage()


@router.get("/budget-anomalies")
async def detect_budget_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_budget_anomalies()


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


eba_route = router
