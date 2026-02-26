"""Audit intelligence analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.audit_intelligence import (
    AuditCategory,
    AuditPattern,
    AuditRiskLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/audit-intelligence",
    tags=["Audit Intelligence"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Audit intelligence service unavailable")
    return _engine


class RecordFindingRequest(BaseModel):
    finding_name: str
    category: AuditCategory = AuditCategory.COMPLIANCE
    risk_level: AuditRiskLevel | None = None
    pattern: AuditPattern = AuditPattern.NORMAL
    affected_resource: str = ""
    deviation_pct: float = 0.0
    details: str = ""


class RecordAnomalyRequest(BaseModel):
    anomaly_name: str
    category: AuditCategory = AuditCategory.COMPLIANCE
    risk_level: AuditRiskLevel = AuditRiskLevel.MEDIUM
    pattern: AuditPattern = AuditPattern.UNUSUAL_TIMING
    baseline_value: float = 0.0
    observed_value: float = 0.0


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
    category: AuditCategory | None = None,
    risk_level: AuditRiskLevel | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_findings(
            category=category,
            risk_level=risk_level,
            limit=limit,
        )
    ]


@router.get("/findings/{record_id}")
async def get_finding(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_finding(record_id)
    if result is None:
        raise HTTPException(404, f"Finding '{record_id}' not found")
    return result.model_dump()


@router.post("/anomalies")
async def record_anomaly(
    body: RecordAnomalyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_anomaly(**body.model_dump())
    return result.model_dump()


@router.get("/patterns/{category}")
async def analyze_audit_patterns(
    category: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_audit_patterns(category)


@router.get("/high-risk")
async def identify_high_risk_findings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_findings()


@router.get("/rankings")
async def rank_by_anomaly_deviation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_anomaly_deviation()


@router.get("/suspicious")
async def detect_suspicious_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_suspicious_patterns()


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


ais_route = router
