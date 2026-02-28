"""Failover coordinator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.failover_coordinator import (
    FailoverRegion,
    FailoverStatus,
    FailoverType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/failover-coordinator",
    tags=["Failover Coordinator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Failover-coordinator service unavailable",
        )
    return _engine


class RecordFailoverRequest(BaseModel):
    service_name: str
    failover_type: FailoverType = FailoverType.DNS_SWITCHOVER
    status: FailoverStatus = FailoverStatus.INITIATED
    region: FailoverRegion = FailoverRegion.US_EAST
    duration_seconds: float = 0.0
    details: str = ""


class AddPlanRequest(BaseModel):
    plan_name: str
    failover_type: FailoverType = FailoverType.DNS_SWITCHOVER
    region: FailoverRegion = FailoverRegion.US_EAST
    rto_seconds: int = 300
    rpo_seconds: float = 60.0


@router.post("/failovers")
async def record_failover(
    body: RecordFailoverRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_failover(**body.model_dump())
    return result.model_dump()


@router.get("/failovers")
async def list_failovers(
    service_name: str | None = None,
    failover_type: FailoverType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_failovers(
            service_name=service_name,
            failover_type=failover_type,
            limit=limit,
        )
    ]


@router.get("/failovers/{record_id}")
async def get_failover(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_failover(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Failover '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/plans")
async def add_plan(
    body: AddPlanRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_plan(**body.model_dump())
    return result.model_dump()


@router.get("/readiness/{service_name}")
async def analyze_failover_readiness(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_failover_readiness(service_name)


@router.get("/failed-failovers")
async def identify_failed_failovers(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failed_failovers()


@router.get("/rankings")
async def rank_by_failover_speed(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_failover_speed()


@router.get("/failover-risks")
async def detect_failover_risks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_failover_risks()


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


mfc_route = router
