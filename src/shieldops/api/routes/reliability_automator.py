"""Reliability automator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.reliability_automator import (
    AdjustmentOutcome,
    AdjustmentTrigger,
    AdjustmentType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/reliability-automator",
    tags=["Reliability Automator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Reliability automator service unavailable")
    return _engine


class RecordAdjustmentRequest(BaseModel):
    service_name: str
    adjustment_type: AdjustmentType = AdjustmentType.TIGHTEN_SLO
    adjustment_trigger: AdjustmentTrigger = AdjustmentTrigger.PERFORMANCE_IMPROVEMENT
    adjustment_outcome: AdjustmentOutcome = AdjustmentOutcome.APPLIED
    impact_score: float = 0.0
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    adjustment_type: AdjustmentType = AdjustmentType.ADD_REDUNDANCY
    adjustment_trigger: AdjustmentTrigger = AdjustmentTrigger.DEGRADATION_DETECTED
    threshold_value: float = 0.0


@router.post("/adjustments")
async def record_adjustment(
    body: RecordAdjustmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_adjustment(**body.model_dump())
    return result.model_dump()


@router.get("/adjustments")
async def list_adjustments(
    service_name: str | None = None,
    adjustment_type: AdjustmentType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_adjustments(
            service_name=service_name, adjustment_type=adjustment_type, limit=limit
        )
    ]


@router.get("/adjustments/{record_id}")
async def get_adjustment(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_adjustment(record_id)
    if result is None:
        raise HTTPException(404, f"Adjustment record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/adjustment-effectiveness/{service_name}")
async def analyze_adjustment_effectiveness(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_adjustment_effectiveness(service_name)


@router.get("/rejected-adjustments")
async def identify_rejected_adjustments(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_rejected_adjustments()


@router.get("/rankings")
async def rank_by_impact_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact_score()


@router.get("/conflicts")
async def detect_adjustment_conflicts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_adjustment_conflicts()


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


rae_route = router
