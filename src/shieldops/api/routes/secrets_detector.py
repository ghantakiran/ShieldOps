"""Secrets sprawl detector API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/secrets-detector", tags=["Secrets Detector"])

_detector: Any = None


def set_detector(detector: Any) -> None:
    global _detector
    _detector = detector


def _get_detector() -> Any:
    if _detector is None:
        raise HTTPException(503, "Secrets detector service unavailable")
    return _detector


class RecordFindingRequest(BaseModel):
    secret_type: str = "API_KEY"  # noqa: S105
    source: str = "GIT_REPOSITORY"
    severity: str = "MEDIUM"
    service_name: str = ""
    file_path: str = ""
    description: str = ""


class RecordRotationRequest(BaseModel):
    finding_id: str
    service_name: str = ""
    rotated_by: str = ""
    rotation_method: str = ""


@router.post("/findings")
async def record_finding(
    body: RecordFindingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    finding = detector.record_finding(**body.model_dump())
    return finding.model_dump()


@router.get("/findings")
async def list_findings(
    secret_type: str | None = None,
    severity: str | None = None,
    is_resolved: bool | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return [
        f.model_dump()
        for f in detector.list_findings(
            secret_type=secret_type, severity=severity, is_resolved=is_resolved, limit=limit
        )
    ]


@router.get("/findings/{finding_id}")
async def get_finding(
    finding_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    finding = detector.get_finding(finding_id)
    if finding is None:
        raise HTTPException(404, f"Finding '{finding_id}' not found")
    return finding.model_dump()


@router.put("/findings/{finding_id}/resolve")
async def resolve_finding(
    finding_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    resolved = detector.resolve_finding(finding_id)
    if not resolved:
        raise HTTPException(404, f"Finding '{finding_id}' not found")
    return {"resolved": True, "finding_id": finding_id}


@router.post("/rotations")
async def record_rotation(
    body: RecordRotationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    rotation = detector.record_rotation(**body.model_dump())
    return rotation.model_dump()


@router.get("/high-risk-services")
async def detect_high_risk_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return detector.detect_high_risk_services()


@router.get("/sprawl-trends")
async def analyze_sprawl_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.analyze_sprawl_trends()


@router.get("/unrotated")
async def identify_unrotated_secrets(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    detector = _get_detector()
    return [f.model_dump() for f in detector.identify_unrotated_secrets()]


@router.get("/report")
async def generate_secrets_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.generate_secrets_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    detector = _get_detector()
    return detector.get_stats()
