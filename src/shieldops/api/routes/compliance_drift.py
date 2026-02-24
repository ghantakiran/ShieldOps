"""Compliance Drift Detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.compliance_drift import (
    DriftCategory,
    DriftSeverity,
    RemediationUrgency,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/compliance-drift",
    tags=["Compliance Drift Detector"],
)

_instance: Any = None


def set_detector(detector: Any) -> None:
    global _instance
    _instance = detector


def _get_detector() -> Any:
    if _instance is None:
        raise HTTPException(503, "Compliance drift service unavailable")
    return _instance


class RecordDriftRequest(BaseModel):
    resource_id: str = ""
    framework: str = ""
    control_id: str = ""
    drift_category: DriftCategory = DriftCategory.CONFIGURATION
    severity: DriftSeverity = DriftSeverity.MINOR
    expected_state: str = ""
    actual_state: str = ""
    remediation_urgency: RemediationUrgency = RemediationUrgency.WITHIN_WEEK


class CreateBaselineRequest(BaseModel):
    framework: str = ""
    control_count: int = 0
    last_audit_at: float = 0.0


class MarkRemediatedRequest(BaseModel):
    drift_id: str


@router.post("/record")
async def record_drift(
    body: RecordDriftRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    record = det.record_drift(**body.model_dump())
    return record.model_dump()


@router.post("/baseline")
async def create_baseline(
    body: CreateBaselineRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    baseline = det.create_baseline(**body.model_dump())
    return baseline.model_dump()


@router.post("/remediated")
async def mark_remediated(
    body: MarkRemediatedRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    record = det.mark_remediated(body.drift_id)
    if record is None:
        raise HTTPException(404, "Drift not found")
    return record.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    return det.get_stats()


@router.get("/report")
async def get_drift_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    return det.generate_drift_report().model_dump()


@router.get("/recurring")
async def get_recurring_drifts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    det = _get_detector()
    return det.identify_recurring_drifts()


@router.get("/compare/{framework}")
async def compare_to_baseline(
    framework: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    return det.compare_to_baseline(framework)


@router.get("/rate/{framework}")
async def get_drift_rate(
    framework: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    return det.calculate_drift_rate(framework)


@router.get("")
async def list_drifts(
    framework: str | None = None,
    severity: DriftSeverity | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    det = _get_detector()
    return [
        d.model_dump()
        for d in det.list_drifts(
            framework=framework,
            severity=severity,
            limit=limit,
        )
    ]


@router.get("/{drift_id}")
async def get_drift(
    drift_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    det = _get_detector()
    record = det.get_drift(drift_id)
    if record is None:
        raise HTTPException(404, f"Drift '{drift_id}' not found")
    return record.model_dump()
