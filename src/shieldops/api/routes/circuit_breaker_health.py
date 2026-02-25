"""Circuit breaker health monitor routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.circuit_breaker_health import (
    BreakerState,
    RecoverySpeed,
    TripReason,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/circuit-breaker-health",
    tags=["Circuit Breaker Health"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Circuit breaker health service unavailable")
    return _engine


class RecordStateRequest(BaseModel):
    service_name: str
    state: BreakerState = BreakerState.CLOSED
    trip_reason: TripReason = TripReason.ERROR_RATE
    error_rate_pct: float = 0.0
    recovery_speed: RecoverySpeed = RecoverySpeed.NORMAL
    details: str = ""


class RecordTransitionRequest(BaseModel):
    service_name: str
    from_state: BreakerState = BreakerState.CLOSED
    to_state: BreakerState = BreakerState.OPEN
    trip_reason: TripReason = TripReason.ERROR_RATE
    duration_seconds: float = 0.0
    details: str = ""


@router.post("/states")
async def record_state(
    body: RecordStateRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_state(**body.model_dump())
    return result.model_dump()


@router.get("/states")
async def list_states(
    service_name: str | None = None,
    state: BreakerState | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_states(service_name=service_name, state=state, limit=limit)
    ]


@router.get("/states/{record_id}")
async def get_state(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_state(record_id)
    if result is None:
        raise HTTPException(404, f"State record '{record_id}' not found")
    return result.model_dump()


@router.post("/transitions")
async def record_transition(
    body: RecordTransitionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_transition(**body.model_dump())
    return result.model_dump()


@router.get("/health/{service_name}")
async def analyze_breaker_health(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_breaker_health(service_name)


@router.get("/frequently-tripping")
async def identify_frequently_tripping(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_frequently_tripping()


@router.get("/slow-recoveries")
async def detect_slow_recoveries(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_slow_recoveries()


@router.get("/impact-rankings")
async def rank_by_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact()


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


cbh_route = router
