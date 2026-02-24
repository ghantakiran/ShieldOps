"""Resilience score calculator API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/resilience-scorer", tags=["Resilience Scorer"])

_scorer: Any = None


def set_scorer(scorer: Any) -> None:
    global _scorer
    _scorer = scorer


def _get_scorer() -> Any:
    if _scorer is None:
        raise HTTPException(503, "Resilience scorer service unavailable")
    return _scorer


class RegisterProfileRequest(BaseModel):
    service_name: str
    redundancy_level: str = "NONE"
    recovery_capability: str = "MANUAL"
    mttr_minutes: float = 0.0
    blast_radius_pct: float = 0.0
    has_circuit_breaker: bool = False
    has_fallback: bool = False
    last_incident_days_ago: int = 0


@router.post("/profiles")
async def register_profile(
    body: RegisterProfileRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    profile = scorer.register_profile(**body.model_dump())
    return profile.model_dump()


@router.get("/profiles")
async def list_profiles(
    redundancy_level: str | None = None,
    recovery_capability: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [
        p.model_dump()
        for p in scorer.list_profiles(
            redundancy_level=redundancy_level,
            recovery_capability=recovery_capability,
            limit=limit,
        )
    ]


@router.get("/profiles/{profile_id}")
async def get_profile(
    profile_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    profile = scorer.get_profile(profile_id)
    if profile is None:
        raise HTTPException(404, f"Profile '{profile_id}' not found")
    return profile.model_dump()


@router.post("/scores/{profile_id}")
async def calculate_score(
    profile_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    score = scorer.calculate_score(profile_id)
    return score.model_dump()


@router.post("/scores/all")
async def calculate_all_scores(
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [s.model_dump() for s in scorer.calculate_all_scores()]


@router.get("/weakest-links")
async def identify_weakest_links(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [s.model_dump() for s in scorer.identify_weakest_links()]


@router.post("/compare")
async def compare_services(
    service_ids: list[str],
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    scorer = _get_scorer()
    return [s.model_dump() for s in scorer.compare_services(service_ids)]


@router.get("/improvements/{profile_id}")
async def recommend_improvements(
    profile_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[str]:
    scorer = _get_scorer()
    return scorer.recommend_improvements(profile_id)


@router.get("/report")
async def generate_resilience_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    return scorer.generate_resilience_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    scorer = _get_scorer()
    return scorer.get_stats()
