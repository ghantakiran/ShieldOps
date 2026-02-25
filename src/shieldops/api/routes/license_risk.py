"""Dependency license risk analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.license_risk import (
    CompatibilityStatus,
    LicenseCategory,
    RiskLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/license-risk",
    tags=["License Risk"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "License risk service unavailable")
    return _engine


class RecordLicenseRequest(BaseModel):
    package_name: str
    version: str = ""
    license_name: str = ""
    category: LicenseCategory = LicenseCategory.UNKNOWN
    risk_level: RiskLevel = RiskLevel.MEDIUM
    transitive_depth: int = 0
    compatibility: CompatibilityStatus = CompatibilityStatus.UNASSESSED
    details: str = ""


class RecordConflictRequest(BaseModel):
    package_a: str
    package_b: str
    license_a: str = ""
    license_b: str = ""
    conflict_reason: str = ""
    risk_level: RiskLevel = RiskLevel.HIGH
    details: str = ""


@router.post("/licenses")
async def record_license(
    body: RecordLicenseRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_license(**body.model_dump())
    return result.model_dump()


@router.get("/licenses")
async def list_licenses(
    package_name: str | None = None,
    category: LicenseCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_licenses(package_name=package_name, category=category, limit=limit)
    ]


@router.get("/licenses/{record_id}")
async def get_license(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_license(record_id)
    if result is None:
        raise HTTPException(404, f"License record '{record_id}' not found")
    return result.model_dump()


@router.post("/conflicts")
async def record_conflict(
    body: RecordConflictRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_conflict(**body.model_dump())
    return result.model_dump()


@router.get("/risk/{package_name}")
async def analyze_license_risk(
    package_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_license_risk(package_name)


@router.get("/copyleft")
async def identify_copyleft_contamination(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_copyleft_contamination()


@router.get("/conflicts")
async def detect_license_conflicts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_license_conflicts()


@router.get("/ranked")
async def rank_by_risk(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk()


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


lr_route = router
