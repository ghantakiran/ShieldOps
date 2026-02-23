"""Cost anomaly detection API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.analytics.cost_anomaly import AnomalyStatus
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/cost-anomaly", tags=["Cost Anomaly"])

_detector: Any = None


def set_detector(detector: Any) -> None:
    global _detector
    _detector = detector


def _get_detector() -> Any:
    if _detector is None:
        raise HTTPException(503, "Cost anomaly service unavailable")
    return _detector


class IngestRequest(BaseModel):
    service: str
    amount: float
    currency: str = "USD"
    date: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateStatusRequest(BaseModel):
    status: AnomalyStatus


@router.post("/ingest")
async def ingest_cost_data(
    body: IngestRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    point = detector.ingest(**body.model_dump())
    return point.model_dump()


@router.get("/detect")
async def detect_anomalies(
    service: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return [a.model_dump() for a in detector.detect_anomalies(service=service)]


@router.get("/anomalies")
async def list_anomalies(
    status: AnomalyStatus | None = None,
    service: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return [
        a.model_dump() for a in detector.list_anomalies(status=status, service=service, limit=limit)
    ]


@router.get("/summary")
async def get_summary(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.get_daily_summary()


@router.get("/anomalies/{anomaly_id}")
async def get_anomaly(
    anomaly_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    anomaly = detector.get_anomaly(anomaly_id)
    if anomaly is None:
        raise HTTPException(404, f"Anomaly '{anomaly_id}' not found")
    return anomaly.model_dump()


@router.put("/anomalies/{anomaly_id}/status")
async def update_anomaly_status(
    anomaly_id: str,
    body: UpdateStatusRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    anomaly = detector.update_status(anomaly_id, body.status)
    if anomaly is None:
        raise HTTPException(404, f"Anomaly '{anomaly_id}' not found")
    return anomaly.model_dump()
