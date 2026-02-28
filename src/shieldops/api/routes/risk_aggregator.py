"""Risk signal aggregator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.risk_aggregator import (
    AggregationMethod,
    SignalDomain,
    SignalSeverity,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/risk-aggregator",
    tags=["Risk Aggregator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Risk aggregator service unavailable")
    return _engine


class RecordSignalRequest(BaseModel):
    service_name: str
    signal_domain: SignalDomain = SignalDomain.SECURITY
    signal_severity: SignalSeverity = SignalSeverity.MEDIUM
    aggregation_method: AggregationMethod = AggregationMethod.WEIGHTED_AVERAGE
    risk_score: float = 0.0
    details: str = ""


class AddScoreRequest(BaseModel):
    score_label: str
    signal_domain: SignalDomain = SignalDomain.SECURITY
    signal_severity: SignalSeverity = SignalSeverity.MEDIUM
    weighted_score: float = 0.0


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
    service_name: str | None = None,
    signal_domain: SignalDomain | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_signals(
            service_name=service_name,
            signal_domain=signal_domain,
            limit=limit,
        )
    ]


@router.get("/signals/{record_id}")
async def get_signal(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_signal(record_id)
    if result is None:
        raise HTTPException(404, f"Signal '{record_id}' not found")
    return result.model_dump()


@router.post("/scores")
async def add_score(
    body: AddScoreRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_score(**body.model_dump())
    return result.model_dump()


@router.get("/service-risk/{service_name}")
async def analyze_service_risk(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_service_risk(service_name)


@router.get("/high-risk-services")
async def identify_high_risk_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_services()


@router.get("/rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/risk-escalations")
async def detect_risk_escalations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_risk_escalations()


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


rsa_route = router
