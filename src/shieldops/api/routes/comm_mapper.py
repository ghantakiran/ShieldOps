"""Service communication mapper API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.comm_mapper import (
    CommHealth,
    CommPattern,
    CommProtocol,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/comm-mapper",
    tags=["Comm Mapper"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Comm mapper service unavailable")
    return _engine


class RecordCommRequest(BaseModel):
    service_name: str
    protocol: CommProtocol = CommProtocol.HTTP
    pattern: CommPattern = CommPattern.SYNCHRONOUS
    health: CommHealth = CommHealth.HEALTHY
    traffic_volume: float = 0.0
    details: str = ""


class AddLinkRequest(BaseModel):
    source_service: str
    target_service: str
    protocol: CommProtocol = CommProtocol.HTTP
    health: CommHealth = CommHealth.HEALTHY
    latency_ms: float = 0.0
    description: str = ""


@router.post("/comms")
async def record_comm(
    body: RecordCommRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_comm(**body.model_dump())
    return result.model_dump()


@router.get("/comms")
async def list_comms(
    service_name: str | None = None,
    protocol: CommProtocol | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_comms(
            service_name=service_name,
            protocol=protocol,
            limit=limit,
        )
    ]


@router.get("/comms/{record_id}")
async def get_comm(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_comm(record_id)
    if result is None:
        raise HTTPException(404, f"Comm record '{record_id}' not found")
    return result.model_dump()


@router.post("/links")
async def add_link(
    body: AddLinkRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_link(**body.model_dump())
    return result.model_dump()


@router.get("/comm-patterns/{service_name}")
async def analyze_comm_patterns(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_comm_patterns(service_name)


@router.get("/unhealthy-links")
async def identify_unhealthy_links(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unhealthy_links()


@router.get("/rankings")
async def rank_by_traffic_volume(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_traffic_volume()


@router.get("/anomalies")
async def detect_comm_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_comm_anomalies()


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


scm_route = router
