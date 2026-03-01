"""Dependency Change Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.dep_change_tracker import (
    ChangeImpact,
    ChangeStatus,
    ChangeType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/dep-change-tracker", tags=["Dependency Change Tracker"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Dependency change tracker service unavailable")
    return _engine


class RecordChangeRequest(BaseModel):
    dependency_name: str
    change_type: ChangeType = ChangeType.ADDED
    change_impact: ChangeImpact = ChangeImpact.NONE
    change_status: ChangeStatus = ChangeStatus.PENDING
    risk_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    dependency_pattern: str
    change_type: ChangeType = ChangeType.ADDED
    max_risk_score: float = 0.0
    auto_approve: bool = False
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
    change_type: ChangeType | None = None,
    impact: ChangeImpact | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_changes(
            change_type=change_type,
            impact=impact,
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
        raise HTTPException(404, f"Change record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/patterns")
async def analyze_change_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_change_patterns()


@router.get("/breaking-changes")
async def identify_breaking_changes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_breaking_changes()


@router.get("/risk-rankings")
async def rank_by_risk_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk_score()


@router.get("/trends")
async def detect_change_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_change_trends()


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


dct_route = router
