"""Reliability target advisor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.reliability_target import BusinessTier

logger = structlog.get_logger()
router = APIRouter(
    prefix="/reliability-target",
    tags=["Reliability Target"],
)

_advisor: Any = None


def set_advisor(advisor: Any) -> None:
    global _advisor
    _advisor = advisor


def _get_advisor() -> Any:
    if _advisor is None:
        raise HTTPException(
            503,
            "Reliability target service unavailable",
        )
    return _advisor


class CreateTargetRequest(BaseModel):
    service_name: str
    business_tier: BusinessTier = BusinessTier.SILVER
    current_reliability_pct: float = 0.0
    dependencies: list[str] | None = None


class RecommendRequest(BaseModel):
    service_name: str
    business_tier: BusinessTier
    historical_pct: float


class AssessRequest(BaseModel):
    actual_pct: float


@router.post("/targets")
async def create_target(
    body: CreateTargetRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    target = advisor.create_target(**body.model_dump())
    return target.model_dump()


@router.get("/targets")
async def list_targets(
    service_name: str | None = None,
    business_tier: BusinessTier | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    advisor = _get_advisor()
    return [
        t.model_dump()
        for t in advisor.list_targets(
            service_name=service_name,
            business_tier=business_tier,
            limit=limit,
        )
    ]


@router.get("/targets/{target_id}")
async def get_target(
    target_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    target = advisor.get_target(target_id)
    if target is None:
        raise HTTPException(404, f"Target '{target_id}' not found")
    return target.model_dump()


@router.post("/recommend")
async def recommend_target(
    body: RecommendRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    target = advisor.recommend_target(
        body.service_name,
        body.business_tier,
        body.historical_pct,
    )
    return target.model_dump()


@router.post("/targets/{target_id}/assess")
async def assess_target(
    target_id: str,
    body: AssessRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    assessment = advisor.assess_target(target_id, body.actual_pct)
    if assessment is None:
        raise HTTPException(404, f"Target '{target_id}' not found")
    return assessment.model_dump()


@router.get("/overcommitted")
async def get_overcommitted(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    advisor = _get_advisor()
    return advisor.identify_overcommitted()


@router.get("/undercommitted")
async def get_undercommitted(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    advisor = _get_advisor()
    return advisor.identify_undercommitted()


@router.get("/dependency-impact")
async def get_dependency_impact(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    advisor = _get_advisor()
    return advisor.analyze_dependency_impact()


@router.get("/report")
async def get_advisor_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    return advisor.generate_advisor_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    advisor = _get_advisor()
    return advisor.get_stats()


@router.post("/clear")
async def clear_data(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, str]:
    advisor = _get_advisor()
    return advisor.clear_data()
