"""Compliance evidence automator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.evidence_automator import (
    ComplianceFramework,
    EvidenceSource,
    EvidenceStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/evidence-automator",
    tags=["Evidence Automator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Evidence-automator service unavailable",
        )
    return _engine


class RecordEvidenceRequest(BaseModel):
    control_name: str
    source: EvidenceSource = EvidenceSource.PLATFORM_TELEMETRY
    status: EvidenceStatus = EvidenceStatus.COLLECTED
    framework: ComplianceFramework = ComplianceFramework.SOC2
    freshness_score: float = 0.0
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    source: EvidenceSource = EvidenceSource.PLATFORM_TELEMETRY
    framework: ComplianceFramework = ComplianceFramework.SOC2
    collection_frequency_hours: int = 24
    retention_days: float = 365.0


@router.post("/evidence")
async def record_evidence(
    body: RecordEvidenceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_evidence(**body.model_dump())
    return result.model_dump()


@router.get("/evidence")
async def list_evidence(
    control_name: str | None = None,
    source: EvidenceSource | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_evidence(
            control_name=control_name,
            source=source,
            limit=limit,
        )
    ]


@router.get("/evidence/{record_id}")
async def get_evidence(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_evidence(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Evidence '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/coverage/{control_name}")
async def analyze_evidence_coverage(
    control_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_evidence_coverage(control_name)


@router.get("/expired-evidence")
async def identify_expired_evidence(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_expired_evidence()


@router.get("/rankings")
async def rank_by_freshness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_freshness()


@router.get("/evidence-gaps")
async def detect_evidence_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_evidence_gaps()


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


cea_route = router
