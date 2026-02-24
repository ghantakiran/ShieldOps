"""Severity calibrator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.severity_calibrator import (
    CalibrationResult,
    ImpactDimension,
    SeverityLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/severity-calibrator",
    tags=["Severity Calibrator"],
)

_calibrator: Any = None


def set_calibrator(calibrator: Any) -> None:
    global _calibrator
    _calibrator = calibrator


def _get_calibrator() -> Any:
    if _calibrator is None:
        raise HTTPException(
            503,
            "Severity calibrator service unavailable",
        )
    return _calibrator


class RecordSeverityRequest(BaseModel):
    incident_id: str
    initial_severity: SeverityLevel
    users_affected: int = 0
    revenue_impact: float = 0.0
    duration_minutes: int = 0


class AddRuleRequest(BaseModel):
    dimension: ImpactDimension
    threshold: float
    maps_to_severity: SeverityLevel
    weight: float = 1.0


@router.post("/records")
async def record_severity(
    body: RecordSeverityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    calibrator = _get_calibrator()
    record = calibrator.record_severity(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_records(
    incident_id: str | None = None,
    calibration_result: CalibrationResult | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    calibrator = _get_calibrator()
    return [
        r.model_dump()
        for r in calibrator.list_records(
            incident_id=incident_id,
            calibration_result=calibration_result,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_record(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    calibrator = _get_calibrator()
    record = calibrator.get_record(record_id)
    if record is None:
        raise HTTPException(404, f"Record '{record_id}' not found")
    return record.model_dump()


@router.post("/records/{record_id}/calibrate")
async def calibrate_severity(
    record_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    calibrator = _get_calibrator()
    result = calibrator.calibrate_severity(record_id)
    if result.get("error"):
        raise HTTPException(404, f"Record '{record_id}' not found")
    return result


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    calibrator = _get_calibrator()
    rule = calibrator.add_calibration_rule(**body.model_dump())
    return rule.model_dump()


@router.get("/accuracy")
async def get_accuracy(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    calibrator = _get_calibrator()
    return calibrator.calculate_accuracy()


@router.get("/drift")
async def get_drift(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    calibrator = _get_calibrator()
    return calibrator.detect_classification_drift()


@router.get("/miscalibrated")
async def get_miscalibrated(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    calibrator = _get_calibrator()
    return calibrator.identify_miscalibrated_services()


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    calibrator = _get_calibrator()
    report = calibrator.generate_calibration_report()
    return report.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    calibrator = _get_calibrator()
    return calibrator.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    calibrator = _get_calibrator()
    return calibrator.clear_data()
