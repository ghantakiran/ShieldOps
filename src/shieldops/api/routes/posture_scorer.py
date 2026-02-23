"""Security posture scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/posture-scores", tags=["Security Posture"])

_scorer: Any = None


def set_scorer(scorer: Any) -> None:
    global _scorer
    _scorer = scorer


def _get_scorer() -> Any:
    if _scorer is None:
        raise HTTPException(503, "Security posture scorer service unavailable")
    return _scorer


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordCheckRequest(BaseModel):
    service: str
    category: str
    check_name: str
    passed: bool = True
    weight: float = 1.0
    details: str = ""


class CompareServicesRequest(BaseModel):
    services: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/checks")
async def record_check(
    body: RecordCheckRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    check = scorer.record_check(**body.model_dump())
    return check.model_dump()


@router.get("/checks")
async def get_checks(
    service: str | None = None,
    category: str | None = None,
    passed: bool | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [
        c.model_dump()
        for c in scorer.get_checks(
            service=service,
            category=category,
            passed=passed,
        )
    ]


@router.post("/calculate/{service}")
async def calculate_score(
    service: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    score = scorer.calculate_score(service)
    return score.model_dump()


@router.get("/scores")
async def list_scores(
    grade: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [s.model_dump() for s in scorer.list_scores(grade=grade)]


@router.get("/scores/{service}")
async def get_score(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    score = scorer.get_score(service)
    if score is None:
        raise HTTPException(404, f"Score for service '{service}' not found")
    return score.model_dump()


@router.get("/scores/{service}/trend")
async def get_trend(
    service: str,
    limit: int = 10,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [s.model_dump() for s in scorer.get_trend(service, limit=limit)]


@router.post("/compare")
async def compare_services(
    body: CompareServicesRequest,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    return scorer.compare_services(body.services)


@router.get("/scores/{service}/worst-categories")
async def get_worst_categories(
    service: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return scorer.get_worst_categories(service)


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    return scorer.get_stats()
