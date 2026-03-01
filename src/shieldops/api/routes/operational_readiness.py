"""Operational Readiness Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.operational_readiness import (
    ReadinessCategory,
    ReadinessGrade,
    ReadinessMaturity,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/operational-readiness",
    tags=["Operational Readiness"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Operational readiness service unavailable")
    return _engine


class RecordReadinessRequest(BaseModel):
    assessment_id: str
    readiness_category: ReadinessCategory = ReadinessCategory.MONITORING
    readiness_grade: ReadinessGrade = ReadinessGrade.ADEQUATE
    readiness_maturity: ReadinessMaturity = ReadinessMaturity.BASIC
    readiness_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddCheckpointRequest(BaseModel):
    assessment_id: str
    readiness_category: ReadinessCategory = ReadinessCategory.MONITORING
    checkpoint_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/readiness")
async def record_readiness(
    body: RecordReadinessRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_readiness(**body.model_dump())
    return result.model_dump()


@router.get("/readiness")
async def list_readiness(
    category: ReadinessCategory | None = None,
    grade: ReadinessGrade | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_readiness(
            category=category,
            grade=grade,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/readiness/{record_id}")
async def get_readiness(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_readiness(record_id)
    if result is None:
        raise HTTPException(404, f"Readiness record '{record_id}' not found")
    return result.model_dump()


@router.post("/checkpoints")
async def add_checkpoint(
    body: AddCheckpointRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_checkpoint(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_readiness_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_readiness_distribution()


@router.get("/failing-services")
async def identify_failing_services(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_failing_services()


@router.get("/readiness-rankings")
async def rank_by_readiness_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_readiness_score()


@router.get("/trends")
async def detect_readiness_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_readiness_trends()


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


opr_route = router
