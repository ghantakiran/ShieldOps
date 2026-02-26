"""Cross-team collaboration scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.collaboration_scorer import (
    CollaborationFrequency,
    CollaborationQuality,
    CollaborationType,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/collaboration-scorer",
    tags=["Collaboration Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Collaboration scorer service unavailable")
    return _engine


class RecordCollaborationRequest(BaseModel):
    team_name: str
    collab_type: CollaborationType = CollaborationType.INCIDENT_RESPONSE
    quality: CollaborationQuality = CollaborationQuality.ADEQUATE
    frequency: CollaborationFrequency = CollaborationFrequency.WEEKLY
    collab_score: float = 0.0
    details: str = ""


class AddMetricRequest(BaseModel):
    metric_name: str
    collab_type: CollaborationType = CollaborationType.INCIDENT_RESPONSE
    quality: CollaborationQuality = CollaborationQuality.ADEQUATE
    score: float = 0.0
    description: str = ""


@router.post("/collaborations")
async def record_collaboration(
    body: RecordCollaborationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_collaboration(**body.model_dump())
    return result.model_dump()


@router.get("/collaborations")
async def list_collaborations(
    team_name: str | None = None,
    collab_type: CollaborationType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_collaborations(
            team_name=team_name,
            collab_type=collab_type,
            limit=limit,
        )
    ]


@router.get("/collaborations/{record_id}")
async def get_collaboration(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_collaboration(record_id)
    if result is None:
        raise HTTPException(404, f"Collaboration '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/team-analysis/{team_name}")
async def analyze_team_collaboration(
    team_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_team_collaboration(team_name)


@router.get("/siloed-teams")
async def identify_siloed_teams(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_siloed_teams()


@router.get("/rankings")
async def rank_by_collaboration_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_collaboration_score()


@router.get("/trends")
async def detect_collaboration_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_collaboration_trends()


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


css_route = router
