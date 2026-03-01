"""Regulatory Change Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.regulation_tracker import (
    ChangeImpact,
    ComplianceAction,
    RegulationType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/regulation-tracker", tags=["Regulation Tracker"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Regulation tracker service unavailable")
    return _engine


class RecordChangeRequest(BaseModel):
    regulation_id: str
    regulation_type: RegulationType = RegulationType.GDPR
    change_impact: ChangeImpact = ChangeImpact.INFORMATIONAL
    compliance_action: ComplianceAction = ComplianceAction.NO_ACTION
    impact_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAnalysisRequest(BaseModel):
    analysis_pattern: str
    regulation_type: RegulationType = RegulationType.GDPR
    urgency_score: float = 0.0
    affected_controls: int = 0
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_change(
    body: RecordChangeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_change(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_changes(
    regulation_type: RegulationType | None = None,
    change_impact: ChangeImpact | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_changes(
            regulation_type=regulation_type,
            change_impact=change_impact,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_change(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_change(record_id)
    if result is None:
        raise HTTPException(404, f"Regulatory record '{record_id}' not found")
    return result.model_dump()


@router.post("/analyses")
async def add_analysis(
    body: AddAnalysisRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_analysis(**body.model_dump())
    return result.model_dump()


@router.get("/impact")
async def analyze_regulatory_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_regulatory_impact()


@router.get("/high-impact")
async def identify_high_impact_changes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_impact_changes()


@router.get("/urgency-rankings")
async def rank_by_urgency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_urgency()


@router.get("/trends")
async def detect_regulatory_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_regulatory_trends()


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


rct_route = router
