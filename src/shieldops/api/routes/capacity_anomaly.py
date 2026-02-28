"""Capacity anomaly detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.capacity_anomaly import (
    AnomalySeverity,
    AnomalyType,
    ResourceType,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/capacity-anomaly",
    tags=["Capacity Anomaly"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Capacity anomaly service unavailable")
    return _engine


class RecordAnomalyRequest(BaseModel):
    service_name: str
    anomaly_type: AnomalyType = AnomalyType.SPIKE
    severity: AnomalySeverity = AnomalySeverity.MODERATE
    resource: ResourceType = ResourceType.CPU
    confidence_pct: float = 0.0
    details: str = ""


class AddPatternRequest(BaseModel):
    pattern_name: str
    anomaly_type: AnomalyType = AnomalyType.SPIKE
    severity: AnomalySeverity = AnomalySeverity.MODERATE
    threshold_value: float = 0.0
    cooldown_minutes: int = 30


@router.post("/anomalies")
async def record_anomaly(
    body: RecordAnomalyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_anomaly(**body.model_dump())
    return result.model_dump()


@router.get("/anomalies")
async def list_anomalies(
    service_name: str | None = None,
    anomaly_type: AnomalyType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_anomalies(
            service_name=service_name, anomaly_type=anomaly_type, limit=limit
        )
    ]


@router.get("/anomalies/{record_id}")
async def get_anomaly(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_anomaly(record_id)
    if result is None:
        raise HTTPException(404, f"Anomaly '{record_id}' not found")
    return result.model_dump()


@router.post("/patterns")
async def add_pattern(
    body: AddPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_pattern(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{service_name}")
async def analyze_anomaly_patterns(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_anomaly_patterns(service_name)


@router.get("/critical-anomalies")
async def identify_critical_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_anomalies()


@router.get("/rankings")
async def rank_by_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact()


@router.get("/recurring-anomalies")
async def detect_recurring_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_recurring_anomalies()


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


cad_route = router
