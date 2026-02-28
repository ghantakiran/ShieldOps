"""Team toil quantifier API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.toil_quantifier import (
    AutomationPotential,
    ToilCategory,
    ToilImpact,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/toil-quantifier",
    tags=["Toil Quantifier"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Toil quantifier service unavailable",
        )
    return _engine


class RecordToilRequest(BaseModel):
    team_name: str
    category: ToilCategory = ToilCategory.MANUAL_DEPLOYMENT
    impact: ToilImpact = ToilImpact.MODERATE
    potential: AutomationPotential = AutomationPotential.PARTIALLY_AUTOMATABLE
    hours_spent: float = 0.0
    details: str = ""


class AddPolicyRequest(BaseModel):
    policy_name: str
    category: ToilCategory = ToilCategory.MANUAL_DEPLOYMENT
    impact: ToilImpact = ToilImpact.MODERATE
    max_toil_hours_weekly: float = 10.0
    automation_target_pct: float = 50.0


@router.post("/toils")
async def record_toil(
    body: RecordToilRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_toil(**body.model_dump())
    return result.model_dump()


@router.get("/toils")
async def list_toils(
    team_name: str | None = None,
    category: ToilCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_toils(
            team_name=team_name,
            category=category,
            limit=limit,
        )
    ]


@router.get("/toils/{record_id}")
async def get_toil(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_toil(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Toil '{record_id}' not found",
        )
    return result.model_dump()


@router.post("/policies")
async def add_policy(
    body: AddPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_policy(**body.model_dump())
    return result.model_dump()


@router.get("/burden/{team_name}")
async def analyze_toil_burden(
    team_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_toil_burden(team_name)


@router.get("/high-toil")
async def identify_high_toil_teams(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_toil_teams()


@router.get("/rankings")
async def rank_by_hours_spent(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_hours_spent()


@router.get("/toil-patterns")
async def detect_toil_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_toil_patterns()


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


ttq_route = router
