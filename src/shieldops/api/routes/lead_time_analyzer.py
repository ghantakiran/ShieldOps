"""Change lead time analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.lead_time_analyzer import (
    LeadTimePhase,
    VelocityGrade,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/lead-time-analyzer",
    tags=["Lead Time Analyzer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Lead time analyzer service unavailable")
    return _engine


class RecordLeadTimeRequest(BaseModel):
    service_name: str
    phase: LeadTimePhase = LeadTimePhase.CODING
    grade: VelocityGrade = VelocityGrade.MEDIUM
    lead_time_hours: float = 0.0
    details: str = ""


class AddBreakdownRequest(BaseModel):
    phase_name: str
    phase: LeadTimePhase = LeadTimePhase.CODING
    grade: VelocityGrade = VelocityGrade.MEDIUM
    avg_hours: float = 0.0
    description: str = ""


@router.post("/lead-times")
async def record_lead_time(
    body: RecordLeadTimeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_lead_time(**body.model_dump())
    return result.model_dump()


@router.get("/lead-times")
async def list_lead_times(
    service_name: str | None = None,
    phase: LeadTimePhase | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_lead_times(
            service_name=service_name,
            phase=phase,
            limit=limit,
        )
    ]


@router.get("/lead-times/{record_id}")
async def get_lead_time(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_lead_time(record_id)
    if result is None:
        raise HTTPException(404, f"Lead time record '{record_id}' not found")
    return result.model_dump()


@router.post("/breakdowns")
async def add_breakdown(
    body: AddBreakdownRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_breakdown(**body.model_dump())
    return result.model_dump()


@router.get("/service-analysis/{service_name}")
async def analyze_service_lead_time(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_service_lead_time(service_name)


@router.get("/slow-services")
async def identify_slow_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_slow_services()


@router.get("/rankings")
async def rank_by_lead_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_lead_time()


@router.get("/trends")
async def detect_lead_time_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_lead_time_trends()


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


lta_route = router
