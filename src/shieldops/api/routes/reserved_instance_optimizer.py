"""Reserved instance optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/reserved-instance-optimizer", tags=["Reserved Instance Optimizer"])

_optimizer: Any = None


def set_optimizer(optimizer: Any) -> None:
    global _optimizer
    _optimizer = optimizer


def _get_optimizer() -> Any:
    if _optimizer is None:
        raise HTTPException(503, "Reserved instance optimizer service unavailable")
    return _optimizer


class RegisterReservationRequest(BaseModel):
    resource_id: str
    commitment_type: str = "RESERVED_INSTANCE"
    instance_type: str = ""
    region: str = ""
    monthly_cost: float = 0.0
    utilization_pct: float = 0.0
    expiry_timestamp: float = 0.0
    coverage_status: str = "UNCOVERED"


@router.post("/reservations")
async def register_reservation(
    body: RegisterReservationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    reservation = optimizer.register_reservation(**body.model_dump())
    return reservation.model_dump()


@router.get("/reservations")
async def list_reservations(
    commitment_type: str | None = None,
    coverage_status: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [
        r.model_dump()
        for r in optimizer.list_reservations(
            commitment_type=commitment_type, coverage_status=coverage_status, limit=limit
        )
    ]


@router.get("/reservations/{reservation_id}")
async def get_reservation(
    reservation_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    reservation = optimizer.get_reservation(reservation_id)
    if reservation is None:
        raise HTTPException(404, f"Reservation '{reservation_id}' not found")
    return reservation.model_dump()


@router.get("/coverage-gaps")
async def analyze_coverage_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [g.model_dump() for g in optimizer.analyze_coverage_gaps()]


@router.get("/expiring")
async def detect_expiring_commitments(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return [r.model_dump() for r in optimizer.detect_expiring_commitments()]


@router.get("/utilization")
async def calculate_utilization_efficiency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.calculate_utilization_efficiency()


@router.get("/purchase-recommendations")
async def recommend_purchases(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    optimizer = _get_optimizer()
    return optimizer.recommend_purchases()


@router.get("/conversion-savings")
async def estimate_savings_from_conversion(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.estimate_savings_from_conversion()


@router.get("/report")
async def generate_optimization_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.generate_optimization_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    optimizer = _get_optimizer()
    return optimizer.get_stats()
