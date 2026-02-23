"""Compliance report generation API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.report_generator import ComplianceFramework, ControlStatus

logger = structlog.get_logger()
router = APIRouter(prefix="/compliance-reports", tags=["Compliance Report Generator"])

_generator: Any = None


def set_generator(generator: Any) -> None:
    global _generator
    _generator = generator


def _get_generator() -> Any:
    if _generator is None:
        raise HTTPException(503, "Compliance report service unavailable")
    return _generator


class GenerateReportRequest(BaseModel):
    framework: ComplianceFramework
    title: str = ""
    control_statuses: dict[str, ControlStatus] = Field(default_factory=dict)
    generated_by: str = ""
    period_start: str = ""
    period_end: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AddEvidenceRequest(BaseModel):
    control_id: str
    description: str
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/generate")
async def generate_report(
    body: GenerateReportRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    report = gen.generate_report(**body.model_dump())
    return report.model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    return gen.get_stats()


@router.get("")
async def list_reports(
    framework: ComplianceFramework | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    gen = _get_generator()
    return [r.model_dump() for r in gen.list_reports(framework=framework, limit=limit)]


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    report = gen.get_report(report_id)
    if report is None:
        raise HTTPException(404, f"Report '{report_id}' not found")
    return report.model_dump()


@router.post("/{report_id}/evidence")
async def add_evidence(
    report_id: str,
    body: AddEvidenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    evidence = gen.add_evidence(report_id, **body.model_dump())
    if evidence is None:
        raise HTTPException(404, "Report or control not found")
    return evidence.model_dump()


@router.get("/{report_id}/score")
async def get_compliance_score(
    report_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    gen = _get_generator()
    score = gen.get_compliance_score(report_id)
    if score is None:
        raise HTTPException(404, f"Report '{report_id}' not found")
    return score
