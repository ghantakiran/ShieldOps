"""Dependency lag monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.dependency_lag import (
    LagCause,
    PropagationDirection,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/dependency-lag",
    tags=["Dependency Lag"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Dependency lag service unavailable",
        )
    return _engine


class RecordLagRequest(BaseModel):
    source_service: str
    target_service: str
    latency_ms: float
    baseline_ms: float = 0.0
    direction: PropagationDirection = PropagationDirection.DOWNSTREAM
    cause: LagCause = LagCause.NETWORK_CONGESTION


class SetBaselineRequest(BaseModel):
    source_service: str
    target_service: str
    baseline_ms: float
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0


@router.post("/records")
async def record_lag(
    body: RecordLagRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_lag(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_lag_records(
    source_service: str | None = None,
    target_service: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_lag_records(
            source_service=source_service,
            target_service=target_service,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_lag_record(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_lag_record(record_id)
    if result is None:
        raise HTTPException(404, f"Lag record '{record_id}' not found")
    return result.model_dump()


@router.post("/baselines")
async def set_baseline(
    body: SetBaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.set_baseline(**body.model_dump())
    return result.model_dump()


@router.get("/degradation/{source_service}/{target_service}")
async def detect_degradation(
    source_service: str,
    target_service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_degradation(source_service, target_service)


@router.get("/propagation/{service}")
async def trace_propagation_chain(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.trace_propagation_chain(service)


@router.get("/bottlenecks")
async def identify_bottleneck_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_bottleneck_services()


@router.get("/compare/{source_service}/{target_service}")
async def compare_to_baseline(
    source_service: str,
    target_service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.compare_to_baseline(source_service, target_service)


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


dl_route = router
