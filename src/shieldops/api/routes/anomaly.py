"""Anomaly detection API endpoints.

Provides routes for running anomaly detection on metric data
and managing statistical baselines.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shieldops.analytics.anomaly import (
    AnomalyDetector,
    Baseline,
    DetectionRequest,
    DetectionResponse,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/anomaly", tags=["Anomaly Detection"])

_detector: AnomalyDetector | None = None


def set_detector(detector: AnomalyDetector | None) -> None:
    """Wire an AnomalyDetector instance into this route module."""
    global _detector
    _detector = detector


def _get_detector() -> AnomalyDetector:
    if _detector is None:
        raise HTTPException(503, "Anomaly detection service unavailable")
    return _detector


class BaselineCreateRequest(BaseModel):
    """Request body for creating/updating a baseline."""

    metric_name: str
    values: list[float]


# ── Endpoints ─────────────────────────────────────────────────────


@router.post("/detect", response_model=DetectionResponse)
async def detect_anomalies(request: DetectionRequest) -> DetectionResponse:
    """Run anomaly detection on the provided metric values."""
    detector = _get_detector()
    try:
        return detector.detect(request)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/baselines", response_model=list[Baseline])
async def list_baselines() -> list[Baseline]:
    """List all stored baselines."""
    detector = _get_detector()
    return detector.list_baselines()


@router.get("/baselines/{metric_name}", response_model=Baseline)
async def get_baseline(metric_name: str) -> Baseline:
    """Get the baseline for a specific metric."""
    detector = _get_detector()
    baseline = detector.get_baseline(metric_name)
    if baseline is None:
        raise HTTPException(404, f"No baseline found for metric '{metric_name}'")
    return baseline


@router.post("/baselines", response_model=Baseline)
async def create_baseline(body: BaselineCreateRequest) -> Baseline:
    """Create or update a baseline from provided values."""
    detector = _get_detector()
    if not body.values:
        raise HTTPException(400, "values list must not be empty")
    return detector.update_baseline(body.metric_name, body.values)
