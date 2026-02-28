"""Compliance report automator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.report_automator import (
    ReportFrequency,
    ReportStatus,
    ReportType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/report-automator",
    tags=["Report Automator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Report automator service unavailable")
    return _engine


class RecordReportRequest(BaseModel):
    report_name: str
    report_type: ReportType = ReportType.SOC2_AUDIT
    status: ReportStatus = ReportStatus.DRAFT
    completion_score: float = 0.0
    frequency: ReportFrequency = ReportFrequency.QUARTERLY
    details: str = ""


class AddSectionRequest(BaseModel):
    section_name: str
    report_type: ReportType = ReportType.SOC2_AUDIT
    status: ReportStatus = ReportStatus.DRAFT
    completion_score: float = 0.0
    description: str = ""


@router.post("/reports")
async def record_report(
    body: RecordReportRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_report(**body.model_dump())
    return result.model_dump()


@router.get("/reports")
async def list_reports(
    report_type: ReportType | None = None,
    status: ReportStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_reports(report_type=report_type, status=status, limit=limit)
    ]


@router.get("/reports/{record_id}")
async def get_report(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_report(record_id)
    if result is None:
        raise HTTPException(404, f"Report record '{record_id}' not found")
    return result.model_dump()


@router.post("/sections")
async def add_section(
    body: AddSectionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_section(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{report_type}")
async def analyze_report_by_type(
    report_type: ReportType,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_report_by_type(report_type)


@router.get("/overdue")
async def identify_overdue_reports(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overdue_reports()


@router.get("/rankings")
async def rank_by_completion_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_completion_score()


@router.get("/gaps")
async def detect_reporting_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_reporting_gaps()


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


cra_route = router
