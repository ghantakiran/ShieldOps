"""Handover Quality Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.handover_quality import (
    HandoverIssue,
    HandoverQuality,
    HandoverType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/handover-quality", tags=["Handover Quality"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Handover quality service unavailable")
    return _engine


class RecordHandoverRequest(BaseModel):
    handover_id: str
    handover_type: HandoverType = HandoverType.SHIFT_CHANGE
    handover_quality: HandoverQuality = HandoverQuality.ADEQUATE
    handover_issue: HandoverIssue = HandoverIssue.MISSING_CONTEXT
    quality_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddChecklistRequest(BaseModel):
    handover_id: str
    handover_type: HandoverType = HandoverType.SHIFT_CHANGE
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_handover(
    body: RecordHandoverRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_handover(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_handovers(
    htype: HandoverType | None = None,
    quality: HandoverQuality | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_handovers(
            htype=htype,
            quality=quality,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_handover(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_handover(record_id)
    if result is None:
        raise HTTPException(404, f"Handover record '{record_id}' not found")
    return result.model_dump()


@router.post("/checklists")
async def add_checklist(
    body: AddChecklistRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_checklist(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_handover_quality(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_handover_quality()


@router.get("/poor-handovers")
async def identify_poor_handovers(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_poor_handovers()


@router.get("/quality-rankings")
async def rank_by_quality_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_quality_score()


@router.get("/issues")
async def detect_handover_issues(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_handover_issues()


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


hqt_route = router
