"""Change Audit Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.change_audit import (
    AuditFinding,
    AuditStatus,
    ChangeType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/change-audit", tags=["Change Audit"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Change audit analyzer service unavailable")
    return _engine


class RecordAuditRequest(BaseModel):
    change_id: str
    change_type: ChangeType = ChangeType.INFRASTRUCTURE
    audit_status: AuditStatus = AuditStatus.PENDING_REVIEW
    audit_finding: AuditFinding = AuditFinding.UNAUTHORIZED_CHANGE
    compliance_pct: float = 0.0
    auditor: str = ""
    model_config = {"extra": "forbid"}


class AddObservationRequest(BaseModel):
    observation_name: str
    change_type: ChangeType = ChangeType.INFRASTRUCTURE
    severity_score: float = 0.0
    changes_reviewed: int = 0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_audit(
    body: RecordAuditRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_audit(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_audits(
    change_type: ChangeType | None = None,
    audit_status: AuditStatus | None = None,
    auditor: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_audits(
            change_type=change_type,
            audit_status=audit_status,
            auditor=auditor,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_audit(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_audit(record_id)
    if result is None:
        raise HTTPException(404, f"Audit record '{record_id}' not found")
    return result.model_dump()


@router.post("/observations")
async def add_observation(
    body: AddObservationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_observation(**body.model_dump())
    return result.model_dump()


@router.get("/compliance")
async def analyze_audit_compliance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_audit_compliance()


@router.get("/non-compliant")
async def identify_non_compliant_changes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_non_compliant_changes()


@router.get("/severity-rankings")
async def rank_by_severity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_severity()


@router.get("/trends")
async def detect_audit_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_audit_trends()


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


cau_route = router
