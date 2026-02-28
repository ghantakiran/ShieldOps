"""Infrastructure cost allocator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.infra_cost_allocator import (
    AllocationAccuracy,
    AllocationMethod,
    CostCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/infra-cost-allocator",
    tags=["Infra Cost Allocator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Infrastructure cost allocator service unavailable",
        )
    return _engine


class RecordAllocationRequest(BaseModel):
    resource_id: str
    resource_name: str = ""
    team: str = ""
    service: str = ""
    cost_category: CostCategory = CostCategory.COMPUTE
    allocation_method: AllocationMethod = AllocationMethod.DIRECT
    total_cost: float = 0.0
    allocated_cost: float = 0.0
    unallocated_cost: float = 0.0
    accuracy: AllocationAccuracy = AllocationAccuracy.HIGH
    details: str = ""


class AddSplitRequest(BaseModel):
    resource_id: str
    team: str = ""
    split_pct: float = 0.0
    split_cost: float = 0.0
    allocation_method: AllocationMethod = AllocationMethod.PROPORTIONAL
    description: str = ""


@router.post("/records")
async def record_allocation(
    body: RecordAllocationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_allocation(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_allocations(
    cost_category: CostCategory | None = None,
    allocation_method: AllocationMethod | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_allocations(
            cost_category=cost_category,
            allocation_method=allocation_method,
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
    record = engine.get_allocation(record_id)
    if record is None:
        raise HTTPException(404, f"Allocation record '{record_id}' not found")
    return record.model_dump()


@router.post("/splits")
async def add_split(
    body: AddSplitRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    split = engine.add_split(**body.model_dump())
    return split.model_dump()


@router.get("/by-team")
async def analyze_allocation_by_team(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_allocation_by_team()


@router.get("/unallocated")
async def identify_unallocated_costs(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unallocated_costs()


@router.get("/rank-by-cost-share")
async def rank_by_cost_share(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_cost_share()


@router.get("/drift")
async def detect_allocation_drift(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_allocation_drift()


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_report()
    return report.model_dump()


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


ica_route = router
