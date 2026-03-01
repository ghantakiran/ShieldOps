"""Access Review Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.access_review import (
    AccessRisk,
    ReviewStatus,
    ReviewType,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/access-review",
    tags=["Access Review"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Access review service unavailable")
    return _engine


class RecordReviewRequest(BaseModel):
    review_id: str
    review_type: ReviewType = ReviewType.QUARTERLY
    review_status: ReviewStatus = ReviewStatus.NOT_STARTED
    access_risk: AccessRisk = AccessRisk.MINIMAL
    completion_pct: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddFindingRequest(BaseModel):
    review_id: str
    review_type: ReviewType = ReviewType.QUARTERLY
    finding_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/reviews")
async def record_review(
    body: RecordReviewRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_review(**body.model_dump())
    return result.model_dump()


@router.get("/reviews")
async def list_reviews(
    review_type: ReviewType | None = None,
    status: ReviewStatus | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_reviews(
            review_type=review_type,
            status=status,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/reviews/{record_id}")
async def get_review(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_review(record_id)
    if result is None:
        raise HTTPException(404, f"Review '{record_id}' not found")
    return result.model_dump()


@router.post("/findings")
async def add_finding(
    body: AddFindingRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_finding(**body.model_dump())
    return result.model_dump()


@router.get("/compliance")
async def analyze_review_compliance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_review_compliance()


@router.get("/overdue")
async def identify_overdue_reviews(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_overdue_reviews()


@router.get("/completion-rankings")
async def rank_by_completion(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_completion()


@router.get("/trends")
async def detect_review_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_review_trends()


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


arv_route = router
