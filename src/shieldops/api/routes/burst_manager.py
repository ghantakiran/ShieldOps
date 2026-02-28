"""Capacity burst manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.burst_manager import (
    BurstAction,
    BurstStatus,
    BurstType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/burst-manager",
    tags=["Burst Manager"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Burst manager service unavailable")
    return _engine


class RecordBurstRequest(BaseModel):
    service_name: str
    burst_type: BurstType = BurstType.TRAFFIC_SPIKE
    action: BurstAction = BurstAction.AUTO_SCALE
    status: BurstStatus = BurstStatus.DETECTED
    cost_impact: float = 0.0
    details: str = ""


class AddPolicyRequest(BaseModel):
    policy_name: str
    burst_type: BurstType = BurstType.TRAFFIC_SPIKE
    action: BurstAction = BurstAction.AUTO_SCALE
    max_scale_factor: int = 3
    budget_limit: float = 1000.0


@router.post("/bursts")
async def record_burst(
    body: RecordBurstRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_burst(**body.model_dump())
    return result.model_dump()


@router.get("/bursts")
async def list_bursts(
    service_name: str | None = None,
    burst_type: BurstType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_bursts(
            service_name=service_name,
            burst_type=burst_type,
            limit=limit,
        )
    ]


@router.get("/bursts/{record_id}")
async def get_burst(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_burst(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Burst '{record_id}' not found",
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


@router.get("/patterns/{service_name}")
async def analyze_burst_patterns(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_burst_patterns(service_name)


@router.get("/budget-overruns")
async def identify_budget_overruns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_budget_overruns()


@router.get("/rankings")
async def rank_by_cost_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_cost_impact()


@router.get("/recurring-bursts")
async def detect_recurring_bursts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_recurring_bursts()


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


cbm_route = router
