"""Escalation optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.escalation_optimizer import (
    EscalationPath,
    OptimizationAction,
    PathEfficiency,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/escalation-optimizer",
    tags=["Escalation Optimizer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Escalation optimizer service unavailable")
    return _engine


class RecordEscalationRequest(BaseModel):
    service_name: str
    path: EscalationPath = EscalationPath.DIRECT_TEAM
    efficiency: PathEfficiency = PathEfficiency.ADEQUATE
    resolution_time_minutes: float = 0.0
    details: str = ""


class AddRecommendationRequest(BaseModel):
    recommendation_name: str
    path: EscalationPath = EscalationPath.DIRECT_TEAM
    action: OptimizationAction = OptimizationAction.NO_CHANGE
    time_saved_minutes: float = 0.0
    description: str = ""


@router.post("/escalations")
async def record_escalation(
    body: RecordEscalationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_escalation(**body.model_dump())
    return result.model_dump()


@router.get("/escalations")
async def list_escalations(
    service_name: str | None = None,
    path: EscalationPath | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_escalations(service_name=service_name, path=path, limit=limit)
    ]


@router.get("/escalations/{record_id}")
async def get_escalation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_escalation(record_id)
    if result is None:
        raise HTTPException(404, f"Escalation '{record_id}' not found")
    return result.model_dump()


@router.post("/recommendations")
async def add_recommendation(
    body: AddRecommendationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_recommendation(**body.model_dump())
    return result.model_dump()


@router.get("/efficiency/{service_name}")
async def analyze_escalation_efficiency(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_escalation_efficiency(service_name)


@router.get("/slow-escalations")
async def identify_slow_escalations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_slow_escalations()


@router.get("/rankings")
async def rank_by_resolution_time(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_resolution_time()


@router.get("/patterns")
async def detect_escalation_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_escalation_patterns()


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


epo_route = router
