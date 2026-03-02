"""Change Rollout Planner API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.change_rollout_planner import (
    RolloutRisk,
    RolloutStage,
    RolloutStrategy,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/change-rollout-planner",
    tags=["Change Rollout Planner"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Change rollout planner service unavailable")
    return _engine


class RecordRolloutRequest(BaseModel):
    change_id: str
    rollout_strategy: RolloutStrategy = RolloutStrategy.CANARY
    rollout_stage: RolloutStage = RolloutStage.PLANNING
    rollout_risk: RolloutRisk = RolloutRisk.CRITICAL
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAssessmentRequest(BaseModel):
    change_id: str
    rollout_strategy: RolloutStrategy = RolloutStrategy.CANARY
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/rollouts")
async def record_rollout(
    body: RecordRolloutRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_rollout(**body.model_dump())
    return result.model_dump()


@router.get("/rollouts")
async def list_rollouts(
    rollout_strategy: RolloutStrategy | None = None,
    rollout_stage: RolloutStage | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_rollouts(
            rollout_strategy=rollout_strategy,
            rollout_stage=rollout_stage,
            team=team,
            limit=limit,
        )
    ]


@router.get("/rollouts/{record_id}")
async def get_rollout(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    found = engine.get_rollout(record_id)
    if found is None:
        raise HTTPException(404, f"Rollout '{record_id}' not found")
    return found.model_dump()


@router.post("/assessments")
async def add_assessment(
    body: AddAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_rollout_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_rollout_distribution()


@router.get("/high-risk-rollouts")
async def identify_high_risk_rollouts(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_risk_rollouts()


@router.get("/risk-rankings")
async def rank_by_risk(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_risk()


@router.get("/trends")
async def detect_rollout_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_rollout_trends()


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


crl_route = router
