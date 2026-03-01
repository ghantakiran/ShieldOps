"""Security Event Correlator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.event_correlator import (
    ChainStage,
    EventSource,
    ThreatLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/event-correlator",
    tags=["Event Correlator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Event correlator service unavailable")
    return _engine


class RecordEventRequest(BaseModel):
    event_id: str
    source: EventSource = EventSource.FIREWALL
    chain_stage: ChainStage = ChainStage.RECONNAISSANCE
    threat_level: ThreatLevel = ThreatLevel.BENIGN
    confidence_score: float = 0.0
    team: str = ""
    details: str = ""
    model_config = {"extra": "forbid"}


class AddChainRequest(BaseModel):
    chain_name: str
    source: EventSource = EventSource.FIREWALL
    chain_stage: ChainStage = ChainStage.RECONNAISSANCE
    event_count: int = 0
    avg_threat_score: float = 0.0
    model_config = {"extra": "forbid"}


@router.post("/events")
async def record_event(
    body: RecordEventRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_event(**body.model_dump())
    return result.model_dump()


@router.get("/events")
async def list_events(
    source: EventSource | None = None,
    chain_stage: ChainStage | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_events(
            source=source,
            chain_stage=chain_stage,
            team=team,
            limit=limit,
        )
    ]


@router.get("/events/{record_id}")
async def get_event(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_event(record_id)
    if result is None:
        raise HTTPException(404, f"Event '{record_id}' not found")
    return result.model_dump()


@router.post("/chains")
async def add_chain(
    body: AddChainRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_chain(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_event_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_event_distribution()


@router.get("/critical-events")
async def identify_critical_events(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_events()


@router.get("/threat-rankings")
async def rank_by_threat_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_threat_score()


@router.get("/trends")
async def detect_event_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_event_trends()


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


sec_route = router
