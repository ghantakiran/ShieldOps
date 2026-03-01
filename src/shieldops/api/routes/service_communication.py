"""Service Communication Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.service_communication import (
    CommunicationHealth,
    CommunicationIssue,
    CommunicationPattern,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/service-communication", tags=["Service Communication"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Service communication service unavailable")
    return _engine


class RecordCommunicationRequest(BaseModel):
    service_name: str
    communication_pattern: CommunicationPattern = CommunicationPattern.SYNCHRONOUS
    communication_health: CommunicationHealth = CommunicationHealth.HEALTHY
    communication_issue: CommunicationIssue = CommunicationIssue.HIGH_LATENCY
    anomaly_rate: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddLinkRequest(BaseModel):
    link_name: str
    communication_pattern: CommunicationPattern = CommunicationPattern.SYNCHRONOUS
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_communication(
    body: RecordCommunicationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_communication(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_communications(
    pattern: CommunicationPattern | None = None,
    health: CommunicationHealth | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_communications(
            pattern=pattern,
            health=health,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_communication(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_communication(record_id)
    if result is None:
        raise HTTPException(404, f"Communication record '{record_id}' not found")
    return result.model_dump()


@router.post("/links")
async def add_link(
    body: AddLinkRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_link(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_communication_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_communication_patterns()


@router.get("/unhealthy-links")
async def identify_unhealthy_links(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unhealthy_links()


@router.get("/reliability-rankings")
async def rank_by_reliability(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_reliability()


@router.get("/anomalies")
async def detect_communication_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_communication_anomalies()


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


sca_route = router
