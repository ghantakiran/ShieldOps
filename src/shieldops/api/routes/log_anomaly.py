"""Log anomaly detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/log-anomaly",
    tags=["Log Anomaly"],
)

_detector: Any = None


def set_detector(detector: Any) -> None:
    global _detector
    _detector = detector


def _get_detector() -> Any:
    if _detector is None:
        raise HTTPException(503, "Log anomaly detector service unavailable")
    return _detector


class RegisterPatternRequest(BaseModel):
    pattern: str
    service: str = ""
    level: str = "info"
    sample_message: str = ""


class SubmitLogBatchRequest(BaseModel):
    service: str
    logs: list[dict[str, Any]]


class SetBaselineRequest(BaseModel):
    pattern: str
    rate: float


@router.post("/patterns")
async def register_pattern(
    body: RegisterPatternRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    pattern = detector.register_pattern(
        pattern=body.pattern,
        service=body.service,
        level=body.level,
        sample_message=body.sample_message,
    )
    return pattern.model_dump()


@router.post("/logs")
async def submit_log_batch(
    body: SubmitLogBatchRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.submit_log_batch(service=body.service, logs=body.logs)


@router.post("/detect")
async def detect_anomalies(
    service: str | None = None,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    anomalies = detector.detect_anomalies(service=service)
    return [a.model_dump() for a in anomalies]


@router.get("/anomalies")
async def list_anomalies(
    service: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    anomalies = detector.list_anomalies(service=service, severity=severity, limit=limit)
    return [a.model_dump() for a in anomalies]


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


@router.post("/baseline")
async def set_baseline(
    body: SetBaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.set_baseline(body.pattern, body.rate)


@router.get("/patterns/{pattern_id}")
async def get_pattern_stats(
    pattern_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    stats = detector.get_pattern_stats(pattern_id)
    if stats is None:
        raise HTTPException(404, f"Pattern '{pattern_id}' not found")
    return stats


@router.post("/anomalies/{anomaly_id}/acknowledge")
async def acknowledge_anomaly(
    anomaly_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    if not detector.acknowledge_anomaly(anomaly_id):
        raise HTTPException(404, f"Anomaly '{anomaly_id}' not found")
    return {"acknowledged": True}


@router.get("/trending")
async def get_trending_patterns(
    limit: int = 10,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return detector.get_trending_patterns(limit=limit)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.get_stats()
