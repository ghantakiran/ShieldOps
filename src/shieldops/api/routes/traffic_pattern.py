"""Traffic pattern analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.traffic_pattern import (
    TrafficAnomaly,
    TrafficDirection,
    TrafficHealth,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/traffic-pattern",
    tags=["Traffic Pattern"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Traffic pattern service unavailable")
    return _engine


class RecordTrafficRequest(BaseModel):
    source_service: str
    dest_service: str = ""
    direction: TrafficDirection = TrafficDirection.INTERNAL
    requests_per_second: float = 0.0
    error_rate_pct: float = 0.0
    p99_latency_ms: float = 0.0
    health: TrafficHealth = TrafficHealth.HEALTHY
    details: str = ""


class RecordAnomalyRequest(BaseModel):
    source_service: str
    dest_service: str = ""
    anomaly_type: TrafficAnomaly = TrafficAnomaly.SPIKE
    severity: float = 0.0
    details: str = ""


@router.post("/traffic")
async def record_traffic(
    body: RecordTrafficRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_traffic(**body.model_dump())
    return result.model_dump()


@router.get("/traffic")
async def list_traffic(
    source_service: str | None = None,
    direction: TrafficDirection | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_traffic(
            source_service=source_service, direction=direction, limit=limit
        )
    ]


@router.get("/traffic/{record_id}")
async def get_traffic(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_traffic(record_id)
    if result is None:
        raise HTTPException(404, f"Traffic record '{record_id}' not found")
    return result.model_dump()


@router.post("/anomalies")
async def record_anomaly(
    body: RecordAnomalyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_anomaly(**body.model_dump())
    return result.model_dump()


@router.get("/service-pair/{source_service}/{dest_service}")
async def analyze_service_pair(
    source_service: str,
    dest_service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_service_pair(source_service, dest_service)


@router.get("/hotspots")
async def identify_hotspots(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_hotspots()


@router.get("/error-prone-routes")
async def detect_error_prone_routes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_error_prone_routes()


@router.get("/latency-ranking")
async def rank_by_latency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_latency()


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


tp_route = router
