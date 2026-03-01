"""Metric anomaly scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.anomaly_scorer import (
    AnomalySeverity,
    AnomalySource,
    AnomalyType,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/anomaly-scorer",
    tags=["Anomaly Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Anomaly scorer service unavailable")
    return _engine


class RecordAnomalyRequest(BaseModel):
    model_config = {"extra": "forbid"}

    metric_name: str
    anomaly_type: AnomalyType = AnomalyType.SPIKE
    severity: AnomalySeverity = AnomalySeverity.NOISE
    source: AnomalySource = AnomalySource.APPLICATION
    anomaly_score: float = 0.0
    service: str = ""
    details: str = ""


class AddContextRequest(BaseModel):
    model_config = {"extra": "forbid"}

    record_id: str
    context_metric: str = ""
    correlation_score: float = 0.0
    description: str = ""


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
    anomaly_type: AnomalyType | None = None,
    severity: AnomalySeverity | None = None,
    source: AnomalySource | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_anomalies(
            anomaly_type=anomaly_type,
            severity=severity,
            source=source,
            limit=limit,
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
        raise HTTPException(404, f"Anomaly record '{record_id}' not found")
    return result.model_dump()


@router.post("/contexts")
async def add_context(
    body: AddContextRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_context(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_anomaly_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_anomaly_patterns()


@router.get("/critical")
async def identify_critical_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_anomalies()


@router.get("/rankings")
async def rank_by_anomaly_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_anomaly_score()


@router.get("/trends")
async def detect_anomaly_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_anomaly_trends()


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


mas_route = router
