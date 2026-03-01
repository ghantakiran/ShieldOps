"""Capacity Scaling Advisor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.capacity_scaling_advisor import (
    ProvisioningStatus,
    ScalingAction,
    ScalingTrigger,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/capacity-scaling-advisor",
    tags=["Capacity Scaling Advisor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Capacity scaling advisor service unavailable")
    return _engine


class RecordScalingRequest(BaseModel):
    scaling_id: str
    scaling_action: ScalingAction = ScalingAction.NO_ACTION
    provisioning_status: ProvisioningStatus = ProvisioningStatus.UNKNOWN
    scaling_trigger: ScalingTrigger = ScalingTrigger.MANUAL
    efficiency_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRecommendationRequest(BaseModel):
    scaling_id: str
    scaling_action: ScalingAction = ScalingAction.NO_ACTION
    recommendation_score: float = 0.0
    threshold: float = 70.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/scalings")
async def record_scaling(
    body: RecordScalingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_scaling(**body.model_dump())
    return result.model_dump()


@router.get("/scalings")
async def list_scalings(
    scaling_action: ScalingAction | None = None,
    provisioning_status: ProvisioningStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_scalings(
            scaling_action=scaling_action,
            provisioning_status=provisioning_status,
            team=team,
            limit=limit,
        )
    ]


@router.get("/scalings/{record_id}")
async def get_scaling(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_scaling(record_id)
    if result is None:
        raise HTTPException(404, f"Scaling '{record_id}' not found")
    return result.model_dump()


@router.post("/recommendations")
async def add_recommendation(
    body: AddRecommendationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_recommendation(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_scaling_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_scaling_distribution()


@router.get("/inefficient-scaling")
async def identify_inefficient_scaling(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_inefficient_scaling()


@router.get("/efficiency-rankings")
async def rank_by_efficiency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_efficiency()


@router.get("/trends")
async def detect_scaling_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_scaling_trends()


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


csa_route = router
