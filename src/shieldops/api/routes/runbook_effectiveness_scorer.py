"""Runbook Effectiveness Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.runbook_effectiveness_scorer import (
    EffectivenessLevel,
    ExecutionOutcome,
    RunbookCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/runbook-effectiveness-scorer",
    tags=["Runbook Effectiveness Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Runbook effectiveness scorer service unavailable")
    return _engine


class RecordEffectivenessRequest(BaseModel):
    runbook_id: str
    effectiveness_level: EffectivenessLevel = EffectivenessLevel.ADEQUATE
    execution_outcome: ExecutionOutcome = ExecutionOutcome.RESOLVED
    runbook_category: RunbookCategory = RunbookCategory.INCIDENT_RESPONSE
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    runbook_id: str
    effectiveness_level: EffectivenessLevel = EffectivenessLevel.ADEQUATE
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/effectiveness")
async def record_effectiveness(
    body: RecordEffectivenessRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_effectiveness(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness")
async def list_effectiveness(
    effectiveness_level: EffectivenessLevel | None = None,
    execution_outcome: ExecutionOutcome | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_effectiveness(
            effectiveness_level=effectiveness_level,
            execution_outcome=execution_outcome,
            team=team,
            limit=limit,
        )
    ]


@router.get("/effectiveness/{record_id}")
async def get_effectiveness(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_effectiveness(record_id)
    if result is None:
        raise HTTPException(404, f"Effectiveness record '{record_id}' not found")
    return result.model_dump()


@router.post("/metrics")
async def add_metric(
    body: AddMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_metric(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_effectiveness_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_effectiveness_distribution()


@router.get("/poor-runbooks")
async def identify_poor_runbooks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_poor_runbooks()


@router.get("/effectiveness-rankings")
async def rank_by_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_effectiveness()


@router.get("/trends")
async def detect_effectiveness_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_effectiveness_trends()


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


res_route = router
