"""Scaling efficiency tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.scaling_efficiency import (
    ScalingOutcome,
    ScalingTrigger,
    ScalingType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/scaling-efficiency",
    tags=["Scaling Efficiency"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Scaling efficiency service unavailable")
    return _engine


class RecordEventRequest(BaseModel):
    service_name: str
    scaling_type: ScalingType = ScalingType.AUTO
    outcome: ScalingOutcome = ScalingOutcome.OPTIMAL
    trigger: ScalingTrigger = ScalingTrigger.CPU_THRESHOLD
    duration_seconds: float = 0.0
    instances_before: int = 0
    instances_after: int = 0
    details: str = ""


class RecordInefficiencyRequest(BaseModel):
    service_name: str
    inefficiency_type: ScalingOutcome = ScalingOutcome.OVER_PROVISIONED
    waste_pct: float = 0.0
    estimated_cost_waste: float = 0.0
    recommendation: str = ""


@router.post("/events")
async def record_event(
    body: RecordEventRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_event(**body.model_dump())
    return result.model_dump()


@router.get("/events")
async def list_events(
    service_name: str | None = None,
    scaling_type: ScalingType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_events(
            service_name=service_name,
            scaling_type=scaling_type,
            limit=limit,
        )
    ]


@router.get("/events/{record_id}")
async def get_event(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_event(record_id)
    if result is None:
        raise HTTPException(404, f"Event '{record_id}' not found")
    return result.model_dump()


@router.post("/inefficiencies")
async def record_inefficiency(
    body: RecordInefficiencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_inefficiency(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{service_name}")
async def analyze_scaling_efficiency(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_scaling_efficiency(service_name)


@router.get("/over-provisioned")
async def identify_over_provisioned(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_over_provisioned()


@router.get("/rankings")
async def rank_by_waste(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_waste()


@router.get("/delays")
async def detect_scaling_delays(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_scaling_delays()


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


sef_route = router
