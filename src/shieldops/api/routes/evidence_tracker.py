"""Audit Evidence Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.evidence_tracker import (
    AuditFramework,
    EvidenceStatus,
    EvidenceType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/evidence-tracker", tags=["Evidence Tracker"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Evidence tracker service unavailable")
    return _engine


class RecordEvidenceRequest(BaseModel):
    control_id: str
    evidence_type: EvidenceType = EvidenceType.SCREENSHOT
    evidence_status: EvidenceStatus = EvidenceStatus.MISSING
    audit_framework: AuditFramework = AuditFramework.SOC2
    completeness_pct: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    framework_pattern: str
    audit_framework: AuditFramework = AuditFramework.SOC2
    required_count: int = 0
    max_age_days: int = 365
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_evidence(
    body: RecordEvidenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_evidence(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_evidence(
    evidence_type: EvidenceType | None = None,
    evidence_status: EvidenceStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_evidence(
            evidence_type=evidence_type,
            evidence_status=evidence_status,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_evidence(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_evidence(record_id)
    if result is None:
        raise HTTPException(404, f"Evidence record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/coverage")
async def analyze_evidence_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_evidence_coverage()


@router.get("/missing")
async def identify_missing_evidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_missing_evidence()


@router.get("/completeness-rankings")
async def rank_by_completeness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_completeness()


@router.get("/trends")
async def detect_evidence_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_evidence_trends()


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


aet_route = router
