"""Prevention engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.prevention_engine import (
    PrecursorType,
    PreventionAction,
    PreventionOutcome,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/prevention-engine",
    tags=["Prevention Engine"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Prevention engine service unavailable")
    return _engine


class RecordPreventionRequest(BaseModel):
    service_name: str
    precursor_type: PrecursorType = PrecursorType.METRIC_ANOMALY
    prevention_action: PreventionAction = PreventionAction.ALERT_TEAM
    prevention_outcome: PreventionOutcome = PreventionOutcome.PREVENTED
    lead_time_minutes: float = 0.0
    details: str = ""


class AddSignalRequest(BaseModel):
    signal_name: str
    precursor_type: PrecursorType = PrecursorType.LOG_PATTERN
    prevention_action: PreventionAction = PreventionAction.AUTO_SCALE
    confidence_score: float = 0.0


@router.post("/preventions")
async def record_prevention(
    body: RecordPreventionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_prevention(**body.model_dump())
    return result.model_dump()


@router.get("/preventions")
async def list_preventions(
    service_name: str | None = None,
    precursor_type: PrecursorType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_preventions(
            service_name=service_name, precursor_type=precursor_type, limit=limit
        )
    ]


@router.get("/preventions/{record_id}")
async def get_prevention(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_prevention(record_id)
    if result is None:
        raise HTTPException(404, f"Prevention '{record_id}' not found")
    return result.model_dump()


@router.post("/signals")
async def add_signal(
    body: AddSignalRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_signal(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness/{service_name}")
async def analyze_prevention_effectiveness(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_prevention_effectiveness(service_name)


@router.get("/missed-preventions")
async def identify_missed_preventions(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_missed_preventions()


@router.get("/rankings")
async def rank_by_lead_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_lead_time()


@router.get("/false-alarms")
async def detect_false_alarm_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_false_alarm_patterns()


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


ipe_route = router
