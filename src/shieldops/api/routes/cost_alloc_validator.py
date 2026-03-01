"""Cost Allocation Validator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.cost_alloc_validator import (
    AllocationStatus,
    AllocationType,
    CostCategory,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/cost-alloc-validator", tags=["Cost Allocation Validator"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cost allocation validator service unavailable")
    return _engine


class RecordAllocationRequest(BaseModel):
    service_name: str
    allocation_type: AllocationType = AllocationType.DIRECT
    status: AllocationStatus = AllocationStatus.PENDING_REVIEW
    cost_category: CostCategory = CostCategory.COMPUTE
    allocated_amount: float = 0.0
    actual_amount: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    service_pattern: str
    allocation_type: AllocationType = AllocationType.DIRECT
    cost_category: CostCategory = CostCategory.COMPUTE
    allocation_pct: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_allocation(
    body: RecordAllocationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_allocation(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_allocations(
    allocation_type: AllocationType | None = None,
    status: AllocationStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_allocations(
            allocation_type=allocation_type,
            status=status,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_allocation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_allocation(record_id)
    if result is None:
        raise HTTPException(404, f"Allocation record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/accuracy")
async def analyze_allocation_accuracy(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_allocation_accuracy()


@router.get("/high-variance")
async def identify_high_variance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_variance()


@router.get("/variance-rankings")
async def rank_by_variance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_variance()


@router.get("/trends")
async def detect_allocation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_allocation_trends()


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


cav_route = router
