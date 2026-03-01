"""Threat Intelligence Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.threat_intelligence import (
    IndicatorType,
    ThreatCategory,
    ThreatSeverity,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/threat-intelligence",
    tags=["Threat Intelligence"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Threat intelligence service unavailable")
    return _engine


class RecordThreatRequest(BaseModel):
    indicator_id: str
    threat_category: ThreatCategory = ThreatCategory.MALWARE
    threat_severity: ThreatSeverity = ThreatSeverity.INFORMATIONAL
    indicator_type: IndicatorType = IndicatorType.IP_ADDRESS
    confidence_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddIndicatorRequest(BaseModel):
    indicator_id: str
    threat_category: ThreatCategory = ThreatCategory.MALWARE
    indicator_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


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
    category: ThreatCategory | None = None,
    severity: ThreatSeverity | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_threats(
            category=category,
            severity=severity,
            service=service,
            team=team,
            limit=limit,
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


@router.post("/indicators")
async def add_indicator(
    body: AddIndicatorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_indicator(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_threat_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_threat_distribution()


@router.get("/critical-threats")
async def identify_critical_threats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_threats()


@router.get("/confidence-rankings")
async def rank_by_confidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_confidence()


@router.get("/trends")
async def detect_threat_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
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


tin_route = router
