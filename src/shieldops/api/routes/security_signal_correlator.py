"""Security Signal Correlator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.security_signal_correlator import (
    CorrelationPattern,
    SignalSource,
    ThreatSeverity,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/security-signal-correlator",
    tags=["Security Signal Correlator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Security signal correlator service unavailable")
    return _engine


class RecordSignalRequest(BaseModel):
    signal_name: str
    signal_source: SignalSource = SignalSource.WAF
    correlation_pattern: CorrelationPattern = CorrelationPattern.LATERAL_MOVEMENT
    threat_severity: ThreatSeverity = ThreatSeverity.CRITICAL
    confidence_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddCorrelationRequest(BaseModel):
    signal_name: str
    signal_source: SignalSource = SignalSource.WAF
    correlation_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/signals")
async def record_signal(
    body: RecordSignalRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_signal(**body.model_dump())
    return result.model_dump()


@router.get("/signals")
async def list_signals(
    signal_source: SignalSource | None = None,
    correlation_pattern: CorrelationPattern | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_signals(
            signal_source=signal_source,
            correlation_pattern=correlation_pattern,
            team=team,
            limit=limit,
        )
    ]


@router.get("/signals/{record_id}")
async def get_signal(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    found = engine.get_signal(record_id)
    if found is None:
        raise HTTPException(404, f"Signal '{record_id}' not found")
    return found.model_dump()


@router.post("/correlations")
async def add_correlation(
    body: AddCorrelationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_correlation(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_signal_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_signal_distribution()


@router.get("/low-confidence-signals")
async def identify_low_confidence_signals(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_confidence_signals()


@router.get("/confidence-rankings")
async def rank_by_confidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_confidence()


@router.get("/trends")
async def detect_signal_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_signal_trends()


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


ssc_route = router
