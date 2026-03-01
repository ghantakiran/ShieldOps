"""Cost Allocation Validator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.cost_allocation_validator import (
    AllocationMethod,
    AllocationStatus,
    CostCenter,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/cost-allocation-validator",
    tags=["Cost Allocation Validator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Cost allocation validator service unavailable")
    return _engine


class RecordAllocationRequest(BaseModel):
    allocation_id: str
    allocation_status: AllocationStatus = AllocationStatus.PENDING
    allocation_method: AllocationMethod = AllocationMethod.TAG_BASED
    cost_center: CostCenter = CostCenter.ENGINEERING
    accuracy_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddCheckRequest(BaseModel):
    allocation_id: str
    allocation_status: AllocationStatus = AllocationStatus.PENDING
    check_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


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
    allocation_status: AllocationStatus | None = None,
    allocation_method: AllocationMethod | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_allocations(
            allocation_status=allocation_status,
            allocation_method=allocation_method,
            team=team,
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
        raise HTTPException(404, f"Allocation '{record_id}' not found")
    return result.model_dump()


@router.post("/checks")
async def add_check(
    body: AddCheckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_check(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_allocation_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_allocation_distribution()


@router.get("/invalid-allocations")
async def identify_invalid_allocations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_invalid_allocations()


@router.get("/accuracy-rankings")
async def rank_by_accuracy(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_accuracy()


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


clv_route = router
