"""Alert Priority Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.alert_priority import (
    OptimizationAction,
    PriorityLevel,
    ResponsePattern,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/alert-priority",
    tags=["Alert Priority"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Alert priority service unavailable",
        )
    return _engine


class RecordPriorityRequest(BaseModel):
    alert_type: str
    current_priority: PriorityLevel = PriorityLevel.INFORMATIONAL
    suggested_priority: PriorityLevel = PriorityLevel.INFORMATIONAL
    action: OptimizationAction = OptimizationAction.MAINTAIN
    response_pattern: ResponsePattern = ResponsePattern.IMMEDIATE
    team: str = ""
    details: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    alert_pattern: str
    priority_level: PriorityLevel = PriorityLevel.INFORMATIONAL
    action: OptimizationAction = OptimizationAction.MAINTAIN
    confidence_pct: float = 0.0
    reason: str = ""
    model_config = {"extra": "forbid"}


@router.post("/priorities")
async def record_priority(
    body: RecordPriorityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_priority(**body.model_dump())
    return result.model_dump()


@router.get("/priorities")
async def list_priorities(
    priority: PriorityLevel | None = None,
    action: OptimizationAction | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_priorities(
            priority=priority,
            action=action,
            team=team,
            limit=limit,
        )
    ]


@router.get("/priorities/{record_id}")
async def get_priority(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_priority(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Priority record '{record_id}' not found",
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


@router.get("/distribution")
async def analyze_priority_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_priority_distribution()


@router.get("/misaligned")
async def identify_misaligned_priorities(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_misaligned_priorities()


@router.get("/misalignment-rankings")
async def rank_by_misalignment(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_misalignment()


@router.get("/trends")
async def detect_priority_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_priority_trends()


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


apo_route = router
