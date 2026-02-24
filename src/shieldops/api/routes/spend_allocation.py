"""Spend allocation engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/spend-allocation", tags=["Spend Allocation"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Spend allocation service unavailable")
    return _engine


class RegisterPoolRequest(BaseModel):
    pool_name: str
    total_cost: float = 0.0
    category: str = "SHARED_INFRASTRUCTURE"
    strategy: str = "EVEN_SPLIT"
    chargeback_model: str = "SHOWBACK"


class AddTeamAllocationRequest(BaseModel):
    pool_id: str
    team_name: str
    allocation_pct: float = 0.0
    usage_units: float = 0.0
    headcount: int = 0


@router.post("/pools")
async def register_pool(
    body: RegisterPoolRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    pool = engine.register_pool(**body.model_dump())
    return pool.model_dump()


@router.get("/pools")
async def list_pools(
    category: str | None = None,
    strategy: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        p.model_dump() for p in engine.list_pools(category=category, strategy=strategy, limit=limit)
    ]


@router.get("/pools/{pool_id}")
async def get_pool(
    pool_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    pool = engine.get_pool(pool_id)
    if pool is None:
        raise HTTPException(404, f"Pool '{pool_id}' not found")
    return pool.model_dump()


@router.post("/allocations")
async def add_team_allocation(
    body: AddTeamAllocationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    allocation = engine.add_team_allocation(**body.model_dump())
    return allocation.model_dump()


@router.post("/calculate/{pool_id}")
async def calculate_allocations(
    pool_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [a.model_dump() for a in engine.calculate_allocations(pool_id)]


@router.get("/team-spend/{team_name}")
async def get_team_total_spend(
    team_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_team_total_spend(team_name)


@router.get("/compare-teams")
async def compare_team_allocations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.compare_team_allocations()


@router.get("/anomalies")
async def detect_allocation_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_allocation_anomalies()


@router.get("/report")
async def generate_allocation_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.generate_allocation_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
