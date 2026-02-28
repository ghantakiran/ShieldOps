"""Service ownership tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.ownership_tracker import (
    EscalationLevel,
    OwnershipRole,
    OwnershipStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/ownership-tracker",
    tags=["Ownership Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Ownership tracker service unavailable")
    return _engine


class RecordOwnershipRequest(BaseModel):
    service_name: str
    role: OwnershipRole = OwnershipRole.PRIMARY_OWNER
    status: OwnershipStatus = OwnershipStatus.ACTIVE
    escalation: EscalationLevel = EscalationLevel.TEAM
    tenure_days: float = 0.0
    details: str = ""


class AddTransferRequest(BaseModel):
    transfer_name: str
    role: OwnershipRole = OwnershipRole.PRIMARY_OWNER
    status: OwnershipStatus = OwnershipStatus.ACTIVE
    from_team: str = ""
    to_team: str = ""


@router.post("/ownerships")
async def record_ownership(
    body: RecordOwnershipRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_ownership(**body.model_dump())
    return result.model_dump()


@router.get("/ownerships")
async def list_ownerships(
    service_name: str | None = None,
    role: OwnershipRole | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_ownerships(service_name=service_name, role=role, limit=limit)
    ]


@router.get("/ownerships/{record_id}")
async def get_ownership(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_ownership(record_id)
    if result is None:
        raise HTTPException(404, f"Ownership '{record_id}' not found")
    return result.model_dump()


@router.post("/transfers")
async def add_transfer(
    body: AddTransferRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_transfer(**body.model_dump())
    return result.model_dump()


@router.get("/health/{service_name}")
async def analyze_ownership_health(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_ownership_health(service_name)


@router.get("/orphaned")
async def identify_orphaned_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_orphaned_services()


@router.get("/rankings")
async def rank_by_ownership_stability(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_ownership_stability()


@router.get("/gaps")
async def detect_ownership_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_ownership_gaps()


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


sot_route = router
