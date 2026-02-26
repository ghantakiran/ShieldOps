"""Automation gap identifier API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.automation_gap import (
    AutomationFeasibility,
    GapCategory,
    GapImpact,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/automation-gap",
    tags=["Automation Gap"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Automation gap service unavailable")
    return _engine


class RecordGapRequest(BaseModel):
    gap_name: str
    category: GapCategory = GapCategory.MANUAL_PROCESS
    feasibility: AutomationFeasibility = AutomationFeasibility.MODERATE
    impact: GapImpact = GapImpact.MEDIUM
    hours_per_week: float = 0.0
    roi_score: float = 0.0
    details: str = ""


class AddCandidateRequest(BaseModel):
    candidate_name: str
    gap_name: str = ""
    feasibility: AutomationFeasibility = AutomationFeasibility.MODERATE
    estimated_savings_hours: float = 0.0
    implementation_effort_days: float = 0.0


@router.post("/gaps")
async def record_gap(
    body: RecordGapRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_gap(**body.model_dump())
    return result.model_dump()


@router.get("/gaps")
async def list_gaps(
    category: GapCategory | None = None,
    feasibility: AutomationFeasibility | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_gaps(
            category=category,
            feasibility=feasibility,
            limit=limit,
        )
    ]


@router.get("/gaps/{record_id}")
async def get_gap(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_gap(record_id)
    if result is None:
        raise HTTPException(404, f"Gap '{record_id}' not found")
    return result.model_dump()


@router.post("/candidates")
async def add_candidate(
    body: AddCandidateRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_candidate(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{category}")
async def analyze_gap_category(
    category: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_gap_category(category)


@router.get("/quick-wins")
async def identify_quick_wins(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_quick_wins()


@router.get("/rankings")
async def rank_by_roi(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_roi()


@router.get("/repetitive")
async def detect_repetitive_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_repetitive_patterns()


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


agp_route = router
