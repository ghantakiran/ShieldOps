"""Team On-Call Equity Analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.oncall_equity import (
    LoadCategory,
    ShiftType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/oncall-equity",
    tags=["On-Call Equity"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "On-call equity service unavailable",
        )
    return _engine


class RecordEquityRequest(BaseModel):
    model_config = {"extra": "forbid"}

    team_member: str
    team: str
    shift_type: ShiftType = ShiftType.WEEKDAY_DAY
    load_category: LoadCategory = LoadCategory.PAGES
    load_count: int = 0
    load_hours: float = 0.0
    equity_score: float = 0.0
    period: str = ""


class AddAdjustmentRequest(BaseModel):
    model_config = {"extra": "forbid"}

    team_member: str
    adjustment_type: str
    reason: str
    shift_change: str


@router.post("/records")
async def record_equity(
    body: RecordEquityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_equity(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_equities(
    shift_type: ShiftType | None = None,
    load_category: LoadCategory | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_equities(
            shift_type=shift_type,
            load_category=load_category,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_equity(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_equity(record_id)
    if record is None:
        raise HTTPException(
            404,
            f"Equity record '{record_id}' not found",
        )
    return record.model_dump()


@router.post("/adjustments")
async def add_adjustment(
    body: AddAdjustmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    adjustment = engine.add_adjustment(**body.model_dump())
    return adjustment.model_dump()


@router.get("/by-team")
async def analyze_equity_by_team(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_equity_by_team()


@router.get("/overloaded")
async def identify_overloaded_members(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overloaded_members()


@router.get("/rank-by-score")
async def rank_by_equity_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_equity_score()


@router.get("/trends")
async def detect_equity_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_equity_trends()


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


oce_route = router
