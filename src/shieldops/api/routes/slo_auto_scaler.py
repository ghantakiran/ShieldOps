"""SLO auto-scaler API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_auto_scaler import (
    ScaleDirection,
    ScaleOutcome,
    ScaleTrigger,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-auto-scaler",
    tags=["SLO Auto-Scaler"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SLO auto-scaler service unavailable")
    return _engine


class RecordScaleRequest(BaseModel):
    service_name: str
    scale_direction: ScaleDirection = ScaleDirection.SCALE_UP
    scale_trigger: ScaleTrigger = ScaleTrigger.BURN_RATE
    scale_outcome: ScaleOutcome = ScaleOutcome.SUCCESSFUL
    replica_delta: int = 0
    details: str = ""


class AddPolicyRequest(BaseModel):
    policy_name: str
    scale_direction: ScaleDirection = ScaleDirection.SCALE_OUT
    scale_trigger: ScaleTrigger = ScaleTrigger.ERROR_BUDGET
    cooldown_seconds: float = 300.0


@router.post("/scales")
async def record_scale(
    body: RecordScaleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_scale(**body.model_dump())
    return result.model_dump()


@router.get("/scales")
async def list_scales(
    service_name: str | None = None,
    scale_direction: ScaleDirection | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_scales(
            service_name=service_name, scale_direction=scale_direction, limit=limit
        )
    ]


@router.get("/scales/{record_id}")
async def get_scale(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_scale(record_id)
    if result is None:
        raise HTTPException(404, f"Scale record '{record_id}' not found")
    return result.model_dump()


@router.post("/policies")
async def add_policy(
    body: AddPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_policy(**body.model_dump())
    return result.model_dump()


@router.get("/scaling-efficiency/{service_name}")
async def analyze_scaling_efficiency(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_scaling_efficiency(service_name)


@router.get("/scaling-failures")
async def identify_scaling_failures(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_scaling_failures()


@router.get("/rankings")
async def rank_by_scale_frequency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_scale_frequency()


@router.get("/oscillations")
async def detect_scaling_oscillations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_scaling_oscillations()


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


sas_route = router
