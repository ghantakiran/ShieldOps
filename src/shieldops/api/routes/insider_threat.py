"""Insider Threat Detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.insider_threat import (
    ThreatCategory,
    ThreatIndicator,
    ThreatLevel,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/insider-threat", tags=["Insider Threat"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Insider threat service unavailable")
    return _engine


class RecordThreatRequest(BaseModel):
    user_id: str
    threat_indicator: ThreatIndicator = ThreatIndicator.UNUSUAL_ACCESS
    threat_level: ThreatLevel = ThreatLevel.LOW
    threat_category: ThreatCategory = ThreatCategory.NEGLIGENT_USER
    threat_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddSignalRequest(BaseModel):
    user_id: str
    threat_indicator: ThreatIndicator = ThreatIndicator.UNUSUAL_ACCESS
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_threat(
    body: RecordThreatRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_threat(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_threats(
    indicator: ThreatIndicator | None = None,
    level: ThreatLevel | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_threats(
            indicator=indicator,
            level=level,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_threat(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_threat(record_id)
    if result is None:
        raise HTTPException(404, f"Threat record '{record_id}' not found")
    return result.model_dump()


@router.post("/signals")
async def add_signal(
    body: AddSignalRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_signal(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_threat_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_threat_patterns()


@router.get("/high-risk-users")
async def identify_high_risk_users(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_users()


@router.get("/score-rankings")
async def rank_by_threat_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_threat_score()


@router.get("/escalation")
async def detect_threat_escalation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_threat_escalation()


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


itd_route = router
