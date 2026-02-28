"""Observability cost allocator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.observability_cost import (
    CostDriver,
    SignalType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/observability-cost",
    tags=["Observability Cost"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Observability cost service unavailable")
    return _engine


class RecordCostRequest(BaseModel):
    team_name: str
    signal_type: SignalType = SignalType.METRICS
    cost_driver: CostDriver = CostDriver.VOLUME
    monthly_cost_usd: float = 0.0
    details: str = ""


class AddAllocationRequest(BaseModel):
    allocation_name: str
    signal_type: SignalType = SignalType.METRICS
    cost_driver: CostDriver = CostDriver.VOLUME
    allocated_amount_usd: float = 0.0
    description: str = ""


@router.post("/costs")
async def record_cost(
    body: RecordCostRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_cost(**body.model_dump())
    return result.model_dump()


@router.get("/costs")
async def list_costs(
    team_name: str | None = None,
    signal_type: SignalType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_costs(
            team_name=team_name,
            signal_type=signal_type,
            limit=limit,
        )
    ]


@router.get("/costs/{record_id}")
async def get_cost(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_cost(record_id)
    if result is None:
        raise HTTPException(404, f"Cost record '{record_id}' not found")
    return result.model_dump()


@router.post("/allocations")
async def add_allocation(
    body: AddAllocationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_allocation(**body.model_dump())
    return result.model_dump()


@router.get("/team-analysis/{team_name}")
async def analyze_team_costs(
    team_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_team_costs(team_name)


@router.get("/high-cost-teams")
async def identify_high_cost_teams(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_cost_teams()


@router.get("/rankings")
async def rank_by_monthly_cost(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_monthly_cost()


@router.get("/trends")
async def detect_cost_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
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


oca_route = router
