"""Access anomaly API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.security.access_anomaly import (
    AccessContext,
    AnomalyType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/access-anomaly",
    tags=["Access Anomaly"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Access anomaly service unavailable",
        )
    return _engine


class RecordAnomalyRequest(BaseModel):
    user_id: str
    anomaly_type: AnomalyType
    context: AccessContext = AccessContext.CORPORATE_NETWORK
    source_ip: str = ""
    location: str = ""
    resource_accessed: str = ""
    threat_score: float = 0.5


class CreateBaselineRequest(BaseModel):
    user_id: str
    usual_hours: list[int] | None = None
    usual_locations: list[str] | None = None
    usual_contexts: list[str] | None = None
    avg_daily_accesses: float = 0.0


class DetectTravelRequest(BaseModel):
    user_id: str
    location_a: str
    location_b: str
    time_diff_minutes: float


class MarkInvestigatedRequest(BaseModel):
    false_positive: bool = False


@router.post("/anomalies")
async def record_anomaly(
    body: RecordAnomalyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_anomaly(**body.model_dump())
    return record.model_dump()


@router.get("/anomalies")
async def list_anomalies(
    user_id: str | None = None,
    anomaly_type: AnomalyType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_anomalies(
            user_id=user_id,
            anomaly_type=anomaly_type,
            limit=limit,
        )
    ]


@router.get("/anomalies/{record_id}")
async def get_anomaly(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_anomaly(record_id)
    if record is None:
        raise HTTPException(404, f"Anomaly '{record_id}' not found")
    return record.model_dump()


@router.post("/anomalies/{record_id}/assess")
async def assess_threat_level(
    record_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.assess_threat_level(record_id)
    return result.model_dump()


@router.post("/baselines")
async def create_baseline(
    body: CreateBaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    baseline = engine.create_baseline(**body.model_dump())
    return baseline.model_dump()


@router.post("/detect-travel")
async def detect_impossible_travel(
    body: DetectTravelRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_impossible_travel(**body.model_dump())


@router.get("/high-risk-users")
async def identify_high_risk_users(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_users()


@router.post("/anomalies/{record_id}/investigate")
async def mark_investigated(
    record_id: str,
    body: MarkInvestigatedRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.mark_investigated(record_id, body.false_positive)
    return result.model_dump()


@router.get("/report")
async def generate_anomaly_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_anomaly_report()
    return report.model_dump()


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


aa_route = router
