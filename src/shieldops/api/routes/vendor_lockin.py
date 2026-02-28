"""Vendor lock-in analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.billing.vendor_lockin import (
    LockinCategory,
    LockinRisk,
    MigrationComplexity,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/vendor-lockin",
    tags=["Vendor Lock-in"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Vendor lock-in analyzer service unavailable")
    return _engine


class RecordLockinRequest(BaseModel):
    vendor_name: str
    service_name: str
    category: LockinCategory = LockinCategory.COMPUTE
    risk: LockinRisk = LockinRisk.MODERATE
    complexity: MigrationComplexity = MigrationComplexity.MODERATE
    risk_score: float = 0.0
    monthly_spend: float = 0.0
    details: str = ""


class AddAssessmentRequest(BaseModel):
    vendor_name: str
    category: LockinCategory = LockinCategory.COMPUTE
    risk: LockinRisk = LockinRisk.MODERATE
    complexity: MigrationComplexity = MigrationComplexity.MODERATE
    estimated_exit_cost: float = 0.0
    notes: str = ""


@router.post("/lockins")
async def record_lockin(
    body: RecordLockinRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_lockin(**body.model_dump())
    return result.model_dump()


@router.get("/lockins")
async def list_lockins(
    vendor_name: str | None = None,
    category: LockinCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_lockins(
            vendor_name=vendor_name,
            category=category,
            limit=limit,
        )
    ]


@router.get("/lockins/{record_id}")
async def get_lockin(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_lockin(record_id)
    if result is None:
        raise HTTPException(404, f"Lock-in record '{record_id}' not found")
    return result.model_dump()


@router.post("/assessments")
async def add_assessment(
    body: AddAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/vendor/{vendor_name}")
async def analyze_lockin_by_vendor(
    vendor_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_lockin_by_vendor(vendor_name)


@router.get("/critical")
async def identify_critical_lockins(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_critical_lockins()


@router.get("/rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/trends")
async def detect_lockin_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_lockin_trends()


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


vla_route = router
