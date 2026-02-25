"""Incident response advisor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/response-advisor",
    tags=["Response Advisor"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Response advisor service unavailable",
        )
    return _engine


class RecordContextRequest(BaseModel):
    incident_id: str
    service: str = ""
    severity: str = "medium"
    blast_radius: int = 1
    error_budget_remaining_pct: float = 100.0
    active_users_affected: int = 0


class GenerateRecommendationRequest(BaseModel):
    incident_id: str


@router.post("/contexts")
async def record_context(
    body: RecordContextRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_context(**body.model_dump())
    return result.model_dump()


@router.get("/contexts")
async def list_contexts(
    incident_id: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [r.model_dump() for r in engine.list_contexts(incident_id=incident_id, limit=limit)]


@router.get("/contexts/{context_id}")
async def get_context(
    context_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_context(context_id)
    if result is None:
        raise HTTPException(404, f"Context '{context_id}' not found")
    return result.model_dump()


@router.post("/recommendations")
async def generate_recommendation(
    body: GenerateRecommendationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.generate_recommendation(body.incident_id)
    return result.model_dump()


@router.get("/recommendations")
async def list_recommendations(
    incident_id: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump() for r in engine.list_recommendations(incident_id=incident_id, limit=limit)
    ]


@router.post("/rank/{incident_id}")
async def rank_strategies(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_strategies(incident_id)


@router.get("/escalation-need/{incident_id}")
async def assess_escalation_need(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.assess_escalation_need(incident_id)


@router.get("/resolution-time/{incident_id}")
async def estimate_resolution_time(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.estimate_resolution_time(incident_id)


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


rad_route = router
