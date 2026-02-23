"""Configuration drift detection API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/drift-detection", tags=["Drift Detection"])

_detector: Any = None


def set_detector(detector: Any) -> None:
    global _detector
    _detector = detector


def _get_detector() -> Any:
    if _detector is None:
        raise HTTPException(503, "Drift detection service unavailable")
    return _detector


class SnapshotRequest(BaseModel):
    environment: str
    config: dict[str, Any]
    service: str = ""
    taken_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DetectRequest(BaseModel):
    source_env: str
    target_env: str
    service: str = ""


class BaselineRequest(BaseModel):
    environment: str
    config: dict[str, Any]
    service: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/snapshots")
async def take_snapshot(
    body: SnapshotRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    snap = detector.take_snapshot(**body.model_dump())
    return snap.model_dump()


@router.post("/detect")
async def detect_drift(
    body: DetectRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    report = detector.detect_drift(**body.model_dump())
    return report.model_dump()


@router.get("/reports")
async def list_reports(
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return [r.model_dump() for r in detector.list_reports(limit=limit)]


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    report = detector.get_report(report_id)
    if report is None:
        raise HTTPException(404, f"Report '{report_id}' not found")
    return report.model_dump()


@router.put("/drifts/{drift_id}/acknowledge")
async def acknowledge_drift(
    drift_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    item = detector.acknowledge_drift(drift_id)
    if item is None:
        raise HTTPException(404, f"Drift '{drift_id}' not found")
    return item.model_dump()


@router.post("/baselines")
async def set_baseline(
    body: BaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    snap = detector.set_baseline(**body.model_dump())
    return snap.model_dump()
