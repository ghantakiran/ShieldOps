"""SLA Impact Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.impact_analyzer import (
    ImpactSeverity,
    ImpactType,
    SLAStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/sla-impact",
    tags=["SLA Impact"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "SLA impact analyzer service unavailable",
        )
    return _engine


class RecordImpactRequest(BaseModel):
    service: str
    impact_type: ImpactType = ImpactType.AVAILABILITY
    severity: ImpactSeverity = ImpactSeverity.NEGLIGIBLE
    sla_status: SLAStatus = SLAStatus.UNKNOWN
    impact_score: float = 0.0
    duration_seconds: float = 0.0
    breached: bool = False
    details: str = ""


class AddContributorRequest(BaseModel):
    contributor_name: str
    impact_type: ImpactType = ImpactType.AVAILABILITY
    severity: ImpactSeverity = ImpactSeverity.NEGLIGIBLE
    contribution_pct: float = 0.0
    service: str = ""
    description: str = ""


@router.post("/records")
async def record_impact(
    body: RecordImpactRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_impact(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_impacts(
    impact_type: ImpactType | None = None,
    severity: ImpactSeverity | None = None,
    sla_status: SLAStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_impacts(
            impact_type=impact_type,
            severity=severity,
            sla_status=sla_status,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_impact(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_impact(record_id)
    if record is None:
        raise HTTPException(404, f"Impact record '{record_id}' not found")
    return record.model_dump()


@router.post("/contributors")
async def add_contributor(
    body: AddContributorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    contributor = engine.add_contributor(**body.model_dump())
    return contributor.model_dump()


@router.get("/by-service")
async def analyze_impact_by_service(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_impact_by_service()


@router.get("/breaches")
async def identify_sla_breaches(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_sla_breaches()


@router.get("/rank-by-severity")
async def rank_by_impact_severity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact_severity()


@router.get("/trends")
async def detect_impact_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_impact_trends()


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_report()
    return report.model_dump()


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


sia_route = router
