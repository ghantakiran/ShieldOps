"""Knowledge contribution tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.knowledge.contribution_tracker import (
    ContributionImpact,
    ContributionQuality,
    ContributionType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/contribution-tracker",
    tags=["Contribution Tracker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Contribution tracker service unavailable")
    return _engine


class RecordContributionRequest(BaseModel):
    contributor_name: str
    contribution_type: ContributionType = ContributionType.DOCUMENTATION
    quality: ContributionQuality = ContributionQuality.ADEQUATE
    impact: ContributionImpact = ContributionImpact.UNKNOWN
    quality_score: float = 0.0
    details: str = ""


class AddContributorProfileRequest(BaseModel):
    profile_name: str
    contribution_type: ContributionType = ContributionType.DOCUMENTATION
    quality: ContributionQuality = ContributionQuality.ADEQUATE
    total_contributions: int = 0
    description: str = ""


@router.post("/contributions")
async def record_contribution(
    body: RecordContributionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_contribution(**body.model_dump())
    return result.model_dump()


@router.get("/contributions")
async def list_contributions(
    contributor_name: str | None = None,
    contribution_type: ContributionType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_contributions(
            contributor_name=contributor_name,
            contribution_type=contribution_type,
            limit=limit,
        )
    ]


@router.get("/contributions/{record_id}")
async def get_contribution(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_contribution(record_id)
    if result is None:
        raise HTTPException(404, f"Contribution '{record_id}' not found")
    return result.model_dump()


@router.post("/profiles")
async def add_contributor_profile(
    body: AddContributorProfileRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_contributor_profile(**body.model_dump())
    return result.model_dump()


@router.get("/patterns/{contributor_name}")
async def analyze_contribution_patterns(
    contributor_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_contribution_patterns(contributor_name)


@router.get("/top-contributors")
async def identify_top_contributors(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_top_contributors()


@router.get("/rankings")
async def rank_by_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_impact()


@router.get("/gaps")
async def detect_knowledge_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_knowledge_gaps()


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


kct_route = router
