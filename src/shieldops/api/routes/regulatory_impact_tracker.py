"""Regulatory Impact Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.regulatory_impact_tracker import (
    ChangeImpact,
    ComplianceReadiness,
    RegulationType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/regulatory-impact-tracker",
    tags=["Regulatory Impact Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Regulatory impact tracker service unavailable")
    return _engine


class RecordRegulatoryRequest(BaseModel):
    regulation_name: str
    regulation_type: RegulationType = RegulationType.DATA_PRIVACY
    change_impact: ChangeImpact = ChangeImpact.MAJOR
    compliance_readiness: ComplianceReadiness = ComplianceReadiness.COMPLIANT
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAnalysisRequest(BaseModel):
    regulation_name: str
    regulation_type: RegulationType = RegulationType.DATA_PRIVACY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/regulatory-records")
async def record_regulatory(
    body: RecordRegulatoryRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_regulatory(**body.model_dump())
    return result.model_dump()


@router.get("/regulatory-records")
async def list_regulatory_records(
    regulation_type: RegulationType | None = None,
    change_impact: ChangeImpact | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_regulatory_records(
            regulation_type=regulation_type,
            change_impact=change_impact,
            team=team,
            limit=limit,
        )
    ]


@router.get("/regulatory-records/{record_id}")
async def get_regulatory(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_regulatory(record_id)
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


@router.get("/distribution")
async def analyze_regulatory_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_regulatory_distribution()


@router.get("/high-impact")
async def identify_high_impact_regulations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_impact_regulations()


@router.get("/impact-rankings")
async def rank_by_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact()


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


rci_route = router
