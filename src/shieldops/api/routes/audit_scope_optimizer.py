"""Audit Scope Optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.audit.audit_scope_optimizer import (
    AssessmentOutcome,
    OptimizationAction,
    ScopeCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/audit-scope-optimizer",
    tags=["Audit Scope Optimizer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Audit scope optimizer service unavailable")
    return _engine


class RecordScopeRequest(BaseModel):
    audit_name: str
    scope_category: ScopeCategory = ScopeCategory.HIGH_RISK
    assessment_outcome: AssessmentOutcome = AssessmentOutcome.FINDING_DENSE
    optimization_action: OptimizationAction = OptimizationAction.EXPAND_SCOPE
    efficiency_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAnalysisRequest(BaseModel):
    audit_name: str
    scope_category: ScopeCategory = ScopeCategory.HIGH_RISK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/scopes")
async def record_scope(
    body: RecordScopeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_scope(**body.model_dump())
    return result.model_dump()


@router.get("/scopes")
async def list_scopes(
    scope_category: ScopeCategory | None = None,
    assessment_outcome: AssessmentOutcome | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_scopes(
            scope_category=scope_category,
            assessment_outcome=assessment_outcome,
            team=team,
            limit=limit,
        )
    ]


@router.get("/scopes/{record_id}")
async def get_scope(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_scope(record_id)
    if result is None:
        raise HTTPException(404, f"Scope record '{record_id}' not found")
    return result.model_dump()


@router.post("/analyses")
async def add_analysis(
    body: AddAnalysisRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_analysis(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_scope_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_scope_distribution()


@router.get("/inefficient-scopes")
async def identify_inefficient_scopes(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_inefficient_scopes()


@router.get("/efficiency-rankings")
async def rank_by_efficiency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_efficiency()


@router.get("/trends")
async def detect_scope_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_scope_trends()


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


aso_route = router
