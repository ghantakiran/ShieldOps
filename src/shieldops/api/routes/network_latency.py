"""Network latency mapper API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.network_latency import (
    LatencyCategory,
    LatencyHealth,
    PathType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/network-latency",
    tags=["Network Latency"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Network latency service unavailable")
    return _engine


class RecordLatencyRequest(BaseModel):
    path_name: str
    category: LatencyCategory = LatencyCategory.INTRA_AZ
    health: LatencyHealth = LatencyHealth.OPTIMAL
    path_type: PathType = PathType.DIRECT
    latency_ms: float = 0.0
    details: str = ""


class AddPathRequest(BaseModel):
    path_name: str
    category: LatencyCategory = LatencyCategory.INTRA_AZ
    health: LatencyHealth = LatencyHealth.OPTIMAL
    source_service: str = ""
    target_service: str = ""


@router.post("/latencies")
async def record_latency(
    body: RecordLatencyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_latency(**body.model_dump())
    return result.model_dump()


@router.get("/latencies")
async def list_latencies(
    path_name: str | None = None,
    category: LatencyCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_latencies(path_name=path_name, category=category, limit=limit)
    ]


@router.get("/latencies/{record_id}")
async def get_latency(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_latency(record_id)
    if result is None:
        raise HTTPException(404, f"Latency '{record_id}' not found")
    return result.model_dump()


@router.post("/paths")
async def add_path(
    body: AddPathRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_path(**body.model_dump())
    return result.model_dump()


@router.get("/health/{path_name}")
async def analyze_network_health(
    path_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_network_health(path_name)


@router.get("/high-latency")
async def identify_high_latency_paths(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_latency_paths()


@router.get("/rankings")
async def rank_by_latency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_latency()


@router.get("/latency-anomalies")
async def detect_latency_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_latency_anomalies()


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


nlm_route = router
