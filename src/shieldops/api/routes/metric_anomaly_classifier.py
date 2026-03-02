"""Metric Anomaly Classifier API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.metric_anomaly_classifier import (
    AnomalyConfidence,
    AnomalyImpact,
    AnomalyType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/metric-anomaly-classifier",
    tags=["Metric Anomaly Classifier"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Metric anomaly classifier service unavailable")
    return _engine


class RecordAnomalyRequest(BaseModel):
    metric_name: str
    anomaly_type: AnomalyType = AnomalyType.SPIKE
    anomaly_confidence: AnomalyConfidence = AnomalyConfidence.VERY_HIGH
    anomaly_impact: AnomalyImpact = AnomalyImpact.CRITICAL
    confidence_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddClassificationRequest(BaseModel):
    metric_name: str
    anomaly_type: AnomalyType = AnomalyType.SPIKE
    classification_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


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
    anomaly_confidence: AnomalyConfidence | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_anomalies(
            anomaly_type=anomaly_type,
            anomaly_confidence=anomaly_confidence,
            team=team,
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
        raise HTTPException(404, f"Anomaly '{record_id}' not found")
    return result.model_dump()


@router.post("/classifications")
async def add_classification(
    body: AddClassificationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_classification(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_anomaly_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_anomaly_distribution()


@router.get("/low-confidence")
async def identify_low_confidence_anomalies(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_low_confidence_anomalies()


@router.get("/confidence-rankings")
async def rank_by_confidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_confidence()


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


mac_route = router
