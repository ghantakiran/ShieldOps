"""Compliance Evidence Consolidator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.evidence_consolidator import (
    ConsolidationLevel,
    EvidenceSource,
    EvidenceStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/evidence-consolidator",
    tags=["Evidence Consolidator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Evidence consolidator service unavailable",
        )
    return _engine


class RecordConsolidationRequest(BaseModel):
    framework: str
    evidence_status: EvidenceStatus = EvidenceStatus.COLLECTED
    source: EvidenceSource = EvidenceSource.AUTOMATED
    consolidation_level: ConsolidationLevel = ConsolidationLevel.PARTIAL
    completeness_pct: float = 0.0
    team: str = ""
    details: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    framework_pattern: str
    evidence_status: EvidenceStatus = EvidenceStatus.COLLECTED
    source: EvidenceSource = EvidenceSource.AUTOMATED
    min_completeness_pct: float = 0.0
    reason: str = ""
    model_config = {"extra": "forbid"}


@router.post("/consolidations")
async def record_consolidation(
    body: RecordConsolidationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_consolidation(**body.model_dump())
    return result.model_dump()


@router.get("/consolidations")
async def list_consolidations(
    status: EvidenceStatus | None = None,
    source: EvidenceSource | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_consolidations(
            status=status,
            source=source,
            team=team,
            limit=limit,
        )
    ]


@router.get("/consolidations/{record_id}")
async def get_consolidation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_consolidation(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Consolidation '{record_id}' not found",
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


@router.get("/coverage")
async def analyze_consolidation_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_consolidation_coverage()


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
async def detect_consolidation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_consolidation_trends()


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


ecn_route = router
