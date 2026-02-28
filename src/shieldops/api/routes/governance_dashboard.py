"""Platform governance dashboard API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.policy.governance_dashboard import (
    GovernanceArea,
    GovernanceStatus,
    GovernanceTrend,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/governance-dashboard",
    tags=["Governance Dashboard"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Governance dashboard unavailable",
        )
    return _engine


class RecordAssessmentRequest(BaseModel):
    area_name: str
    area: GovernanceArea = GovernanceArea.SECURITY
    status: GovernanceStatus = GovernanceStatus.GOOD
    trend: GovernanceTrend = GovernanceTrend.STABLE
    score_pct: float = 0.0
    details: str = ""


class AddPolicyRequest(BaseModel):
    policy_name: str
    area: GovernanceArea = GovernanceArea.SECURITY
    status: GovernanceStatus = GovernanceStatus.GOOD
    min_score_pct: float = 70.0
    review_cadence_days: float = 7.0


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
    area_name: str | None = None,
    area: GovernanceArea | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_assessments(
            area_name=area_name,
            area=area,
            limit=limit,
        )
    ]


@router.get("/assessments/{record_id}")
async def get_assessment(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_assessment(record_id)
    if result is None:
        raise HTTPException(
            404,
            f"Assessment '{record_id}' not found",
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


@router.get("/health/{area_name}")
async def analyze_governance_health(
    area_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_governance_health(area_name)


@router.get("/at-risk")
async def identify_at_risk_areas(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_at_risk_areas()


@router.get("/rankings")
async def rank_by_governance_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_governance_score()


@router.get("/governance-gaps")
async def detect_governance_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_governance_gaps()


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


pgd_route = router
