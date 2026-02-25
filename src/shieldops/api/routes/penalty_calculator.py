"""Penalty calculator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.penalty_calculator import (
    ContractType,
    PenaltyStatus,
    PenaltyTier,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/penalty-calculator",
    tags=["Penalty Calculator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Penalty calculator service unavailable",
        )
    return _engine


class RecordPenaltyRequest(BaseModel):
    customer_id: str
    service_name: str
    contract_type: ContractType
    sla_target_pct: float
    actual_pct: float
    breach_duration_minutes: float
    monthly_revenue: float


class CalculatePenaltyRequest(BaseModel):
    sla_target_pct: float
    actual_pct: float
    monthly_revenue: float
    contract_type: ContractType = ContractType.STANDARD


class SetThresholdRequest(BaseModel):
    contract_type: ContractType
    tier_1_breach_pct: float = 0.1
    tier_2_breach_pct: float = 0.5
    tier_3_breach_pct: float = 1.0
    tier_4_breach_pct: float = 5.0
    tier_1_credit_pct: float = 5.0
    tier_2_credit_pct: float = 10.0
    tier_3_credit_pct: float = 25.0
    tier_4_credit_pct: float = 50.0


class UpdateStatusRequest(BaseModel):
    status: PenaltyStatus


@router.post("/penalties")
async def record_penalty(
    body: RecordPenaltyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_penalty(**body.model_dump())
    return record.model_dump()


@router.get("/penalties")
async def list_penalties(
    customer_id: str | None = None,
    tier: PenaltyTier | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_penalties(
            customer_id=customer_id,
            tier=tier,
            limit=limit,
        )
    ]


@router.get("/penalties/{record_id}")
async def get_penalty(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_penalty(record_id)
    if record is None:
        raise HTTPException(404, f"Penalty '{record_id}' not found")
    return record.model_dump()


@router.post("/calculate")
async def calculate_penalty(
    body: CalculatePenaltyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_penalty(**body.model_dump())


@router.post("/thresholds")
async def set_threshold(
    body: SetThresholdRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    threshold = engine.set_threshold(**body.model_dump())
    return threshold.model_dump()


@router.get("/exposure")
async def estimate_total_exposure(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.estimate_total_exposure()


@router.get("/high-risk-customers")
async def identify_high_risk_customers(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_customers()


@router.post("/penalties/{record_id}/status")
async def update_status(
    record_id: str,
    body: UpdateStatusRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.update_status(record_id, body.status)
    if result is None:
        raise HTTPException(404, f"Penalty '{record_id}' not found")
    return result.model_dump()


@router.get("/report")
async def generate_penalty_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_penalty_report()
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


pc_route = router
