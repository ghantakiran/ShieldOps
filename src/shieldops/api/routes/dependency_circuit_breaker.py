"""Dependency Circuit Breaker Monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.dependency_circuit_breaker import (
    CircuitState,
    RecoveryStrategy,
    TripReason,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dependency-circuit-breaker",
    tags=["Dependency Circuit Breaker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Dependency circuit breaker service unavailable")
    return _engine


class RecordCircuitRequest(BaseModel):
    circuit_id: str
    circuit_state: CircuitState = CircuitState.CLOSED
    trip_reason: TripReason = TripReason.TIMEOUT
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.AUTOMATIC
    trip_count: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddEventRequest(BaseModel):
    circuit_id: str
    circuit_state: CircuitState = CircuitState.CLOSED
    event_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/circuits")
async def record_circuit(
    body: RecordCircuitRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_circuit(**body.model_dump())
    return result.model_dump()


@router.get("/circuits")
async def list_circuits(
    state: CircuitState | None = None,
    reason: TripReason | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_circuits(
            state=state,
            reason=reason,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/circuits/{record_id}")
async def get_circuit(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_circuit(record_id)
    if result is None:
        raise HTTPException(404, f"Circuit record '{record_id}' not found")
    return result.model_dump()


@router.post("/events")
async def add_event(
    body: AddEventRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_event(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_circuit_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_circuit_distribution()


@router.get("/open-circuits")
async def identify_open_circuits(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_open_circuits()


@router.get("/trip-rankings")
async def rank_by_trip_count(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_trip_count()


@router.get("/trends")
async def detect_circuit_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_circuit_trends()


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


dcb_route = router
