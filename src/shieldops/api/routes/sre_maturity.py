"""SRE maturity assessor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.sre_maturity import (
    AssessmentScope,
    MaturityDimension,
    MaturityTier,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/sre-maturity",
    tags=["SRE Maturity"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SRE maturity service unavailable")
    return _engine


class RecordAssessmentRequest(BaseModel):
    entity: str
    dimension: MaturityDimension = MaturityDimension.ONCALL
    scope: AssessmentScope = AssessmentScope.TEAM
    tier: MaturityTier = MaturityTier.INITIAL
    details: str = ""


class AddRoadmapItemRequest(BaseModel):
    entity: str
    dimension: MaturityDimension = MaturityDimension.ONCALL
    current_tier: MaturityTier = MaturityTier.INITIAL
    target_tier: MaturityTier = MaturityTier.DEFINED
    recommendation: str = ""
    effort: str = "medium"


@router.post("/assessments")
async def record_assessment(
    body: RecordAssessmentRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_assessment(**body.model_dump())
    return result.model_dump()


@router.get("/assessments")
async def list_assessments(
    entity: str | None = None,
    dimension: MaturityDimension | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_assessments(entity=entity, dimension=dimension, limit=limit)
    ]


@router.get("/assessments/{record_id}")
async def get_assessment(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_assessment(record_id)
    if result is None:
        raise HTTPException(404, f"Assessment '{record_id}' not found")
    return result.model_dump()


@router.post("/roadmap")
async def add_roadmap_item(
    body: AddRoadmapItemRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_roadmap_item(**body.model_dump())
    return result.model_dump()


@router.get("/maturity/{entity}")
async def calculate_overall_maturity(
    entity: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_overall_maturity(entity)


@router.get("/gaps")
async def identify_maturity_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_maturity_gaps()


@router.get("/roadmap/{entity}")
async def generate_roadmap(
    entity: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.generate_roadmap(entity)


@router.get("/rankings")
async def rank_teams_by_maturity(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_teams_by_maturity()


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


sm_route = router
