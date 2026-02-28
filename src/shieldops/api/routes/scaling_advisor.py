"""Predictive scaling advisor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.scaling_advisor import (
    ScalingAction,
    ScalingConfidence,
    ScalingTrigger,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/scaling-advisor",
    tags=["Scaling Advisor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Scaling advisor service unavailable")
    return _engine


class RecordScalingRequest(BaseModel):
    service_name: str
    action: ScalingAction = ScalingAction.NO_ACTION
    trigger: ScalingTrigger = ScalingTrigger.CPU_THRESHOLD
    confidence: ScalingConfidence = ScalingConfidence.MODERATE
    confidence_pct: float = 0.0
    details: str = ""


class AddRecommendationRequest(BaseModel):
    service_name: str
    action: ScalingAction = ScalingAction.NO_ACTION
    trigger: ScalingTrigger = ScalingTrigger.CPU_THRESHOLD
    savings_potential: float = 0.0
    description: str = ""


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
    service_name: str | None = None,
    action: ScalingAction | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_scalings(
            service_name=service_name,
            action=action,
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
        raise HTTPException(404, f"Scaling record '{record_id}' not found")
    return result.model_dump()


@router.post("/recommendations")
async def add_recommendation(
    body: AddRecommendationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_recommendation(**body.model_dump())
    return result.model_dump()


@router.get("/scaling-patterns/{service_name}")
async def analyze_scaling_patterns(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_scaling_patterns(service_name)


@router.get("/over-provisioned")
async def identify_over_provisioned(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_over_provisioned()


@router.get("/savings-rankings")
async def rank_by_savings_potential(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_savings_potential()


@router.get("/anomalies")
async def detect_scaling_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_scaling_anomalies()


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


psa_route = router
