"""Runbook Compliance Checker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.runbook_compliance import (
    CheckStatus,
    ComplianceArea,
    ComplianceGrade,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/runbook-compliance", tags=["Runbook Compliance"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Runbook compliance service unavailable")
    return _engine


class RecordCheckRequest(BaseModel):
    runbook_id: str
    compliance_area: ComplianceArea = ComplianceArea.DOCUMENTATION
    compliance_grade: ComplianceGrade = ComplianceGrade.F
    check_status: CheckStatus = CheckStatus.PENDING
    score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddStandardRequest(BaseModel):
    standard_name: str
    compliance_area: ComplianceArea = ComplianceArea.DOCUMENTATION
    required_score: float = 0.0
    mandatory: bool = True
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_check(
    body: RecordCheckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_check(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_checks(
    area: ComplianceArea | None = None,
    grade: ComplianceGrade | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_checks(
            area=area,
            grade=grade,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_check(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_check(record_id)
    if result is None:
        raise HTTPException(404, f"Compliance record '{record_id}' not found")
    return result.model_dump()


@router.post("/standards")
async def add_standard(
    body: AddStandardRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_standard(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_compliance_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_compliance_distribution()


@router.get("/failing-runbooks")
async def identify_failing_runbooks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failing_runbooks()


@router.get("/score-rankings")
async def rank_by_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_score()


@router.get("/trends")
async def detect_compliance_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_compliance_trends()


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


rcp_route = router
