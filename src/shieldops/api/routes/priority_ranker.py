"""Incident priority ranker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.priority_ranker import (
    PriorityFactor,
    PriorityLevel,
    RankingMethod,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/priority-ranker",
    tags=["Priority Ranker"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Priority ranker service unavailable",
        )
    return _engine


class RecordPriorityRequest(BaseModel):
    incident_id: str
    incident_title: str = ""
    assigned_priority: PriorityLevel = PriorityLevel.P2_MEDIUM
    computed_priority: PriorityLevel = PriorityLevel.P2_MEDIUM
    ranking_method: RankingMethod = RankingMethod.WEIGHTED_SCORE
    priority_score: float = 0.0
    factors_used: list[str] = []
    is_misranked: bool = False
    details: str = ""


class AddFactorRequest(BaseModel):
    factor_name: str
    factor_type: PriorityFactor = PriorityFactor.USER_IMPACT
    weight: float = 1.0
    description: str = ""
    enabled: bool = True


@router.post("/records")
async def record_priority(
    body: RecordPriorityRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_priority(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_priorities(
    assigned_priority: PriorityLevel | None = None,
    ranking_method: RankingMethod | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_priorities(
            assigned_priority=assigned_priority,
            ranking_method=ranking_method,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_priority(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_priority(record_id)
    if record is None:
        raise HTTPException(404, f"Priority record '{record_id}' not found")
    return record.model_dump()


@router.post("/factors")
async def add_factor(
    body: AddFactorRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    factor = engine.add_factor(**body.model_dump())
    return factor.model_dump()


@router.get("/distribution")
async def analyze_priority_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_priority_distribution()


@router.get("/misranked")
async def identify_misranked_incidents(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_misranked_incidents()


@router.get("/rank-by-score")
async def rank_by_priority_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_priority_score()


@router.get("/drift")
async def detect_priority_drift(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_priority_drift()


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_report()
    return report.model_dump()


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


ipr_route = router
