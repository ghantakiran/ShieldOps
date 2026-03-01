"""Threat intelligence correlator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.threat_correlator import (
    ThreatRelevance,
    ThreatSeverity,
    ThreatSource,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/threat-correlator",
    tags=["Threat Correlator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Threat correlator service unavailable")
    return _engine


class RecordThreatRequest(BaseModel):
    model_config = {"extra": "forbid"}

    threat_id: str
    source: ThreatSource = ThreatSource.EXTERNAL_FEED
    severity: ThreatSeverity = ThreatSeverity.LOW
    relevance: ThreatRelevance = ThreatRelevance.POTENTIAL
    relevance_score: float = 0.0
    affected_service: str = ""
    details: str = ""


class AddCorrelationRequest(BaseModel):
    model_config = {"extra": "forbid"}

    threat_record_id: str
    correlated_threat_id: str = ""
    correlation_score: float = 0.0
    correlation_type: str = ""


@router.post("/threats")
async def record_threat(
    body: RecordThreatRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_threat(**body.model_dump())
    return result.model_dump()


@router.get("/threats")
async def list_threats(
    source: ThreatSource | None = None,
    severity: ThreatSeverity | None = None,
    relevance: ThreatRelevance | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_threats(
            source=source, severity=severity, relevance=relevance, limit=limit
        )
    ]


@router.get("/threats/{record_id}")
async def get_threat(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_threat(record_id)
    if result is None:
        raise HTTPException(404, f"Threat record '{record_id}' not found")
    return result.model_dump()


@router.post("/correlations")
async def add_correlation(
    body: AddCorrelationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_correlation(**body.model_dump())
    return result.model_dump()


@router.get("/landscape")
async def analyze_threat_landscape(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_threat_landscape()


@router.get("/critical")
async def identify_critical_threats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_threats()


@router.get("/rankings")
async def rank_by_relevance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_relevance()


@router.get("/trends")
async def detect_threat_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_threat_trends()


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


tic_route = router
