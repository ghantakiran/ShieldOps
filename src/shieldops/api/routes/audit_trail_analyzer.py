"""Compliance audit trail analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.audit_trail_analyzer import (
    AuditPatternType,
    AuditScope,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/audit-trail-analyzer",
    tags=["Audit Trail Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Audit trail analyzer service unavailable",
        )
    return _engine


class RecordFindingRequest(BaseModel):
    scope: AuditScope
    pattern_type: AuditPatternType
    actor: str = ""
    resource: str = ""
    description: str = ""
    severity_score: float = 0.5


class EvaluateCompletenessRequest(BaseModel):
    scope: AuditScope
    total_expected_events: int = 100
    total_actual_events: int = 100


@router.post("/findings")
async def record_finding(
    body: RecordFindingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_finding(**body.model_dump())
    return result.model_dump()


@router.get("/findings")
async def list_findings(
    scope: AuditScope | None = None,
    pattern_type: AuditPatternType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_findings(scope=scope, pattern_type=pattern_type, limit=limit)
    ]


@router.get("/findings/{finding_id}")
async def get_finding(
    finding_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_finding(finding_id)
    if result is None:
        raise HTTPException(404, f"Finding '{finding_id}' not found")
    return result.model_dump()


@router.post("/completeness")
async def evaluate_completeness(
    body: EvaluateCompletenessRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.evaluate_completeness(**body.model_dump())
    return result.model_dump()


@router.get("/gaps")
async def detect_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_gaps()


@router.get("/suspicious-patterns")
async def detect_suspicious_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_suspicious_patterns()


@router.get("/integrity")
async def score_audit_integrity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.score_audit_integrity()


@router.get("/actors-of-concern")
async def identify_actors_of_concern(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_actors_of_concern()


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


ata_route = router
