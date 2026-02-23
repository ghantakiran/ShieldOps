"""Capacity reservation API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/capacity-reservations", tags=["Capacity Reservations"])

_manager: Any = None


def set_manager(manager: Any) -> None:
    global _manager
    _manager = manager


def _get_manager() -> Any:
    if _manager is None:
        raise HTTPException(503, "Capacity reservation service unavailable")
    return _manager


class ResourceRequest(BaseModel):
    resource_type: str = "cpu"
    amount: float = 1.0
    unit: str = "cores"


class CreateReservationRequest(BaseModel):
    name: str
    resources: list[ResourceRequest]
    start_time: float
    end_time: float
    team: str = ""
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConflictCheckRequest(BaseModel):
    start_time: float
    end_time: float
    resources: list[ResourceRequest]


@router.post("")
async def create_reservation(
    body: CreateReservationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    data = body.model_dump()
    reservation = mgr.create_reservation(**data)
    return reservation.model_dump()


@router.get("")
async def list_reservations(
    status: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    return [r.model_dump() for r in mgr.list_reservations(status=status)]


@router.get("/{reservation_id}")
async def get_reservation(
    reservation_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    res = mgr.get_reservation(reservation_id)
    if res is None:
        raise HTTPException(404, f"Reservation '{reservation_id}' not found")
    return res.model_dump()


@router.put("/{reservation_id}/approve")
async def approve_reservation(
    reservation_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    res = mgr.approve_reservation(reservation_id)
    if res is None:
        raise HTTPException(404, f"Reservation '{reservation_id}' not found or not pending")
    return res.model_dump()


@router.put("/{reservation_id}/activate")
async def activate_reservation(
    reservation_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    res = mgr.activate_reservation(reservation_id)
    if res is None:
        raise HTTPException(404, f"Reservation '{reservation_id}' not found or not approved")
    return res.model_dump()


@router.delete("/{reservation_id}")
async def cancel_reservation(
    reservation_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    res = mgr.cancel_reservation(reservation_id)
    if res is None:
        raise HTTPException(404, f"Reservation '{reservation_id}' not found")
    return res.model_dump()


@router.post("/conflict-check")
async def check_conflicts(
    body: ConflictCheckRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    mgr = _get_manager()
    data = body.model_dump()
    conflicts = mgr.check_conflicts(**data)
    return [c.model_dump() for c in conflicts]


@router.get("/utilization")
async def get_utilization(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_utilization()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    mgr = _get_manager()
    return mgr.get_stats()
