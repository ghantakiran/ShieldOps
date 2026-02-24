"""Runbook effectiveness analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/runbook-effectiveness", tags=["Runbook Effectiveness"])

_analyzer: Any = None


def set_analyzer(analyzer: Any) -> None:
    global _analyzer
    _analyzer = analyzer


def _get_analyzer() -> Any:
    if _analyzer is None:
        raise HTTPException(503, "Runbook effectiveness service unavailable")
    return _analyzer


class RecordOutcomeRequest(BaseModel):
    runbook_id: str
    runbook_name: str = ""
    executed_by: str = ""
    success: bool = True
    execution_time_seconds: float = 0.0
    failure_reason: str | None = None
    notes: str = ""


@router.post("/outcomes")
async def record_outcome(
    body: RecordOutcomeRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    outcome = analyzer.record_outcome(**body.model_dump())
    return outcome.model_dump()


@router.get("/outcomes")
async def list_outcomes(
    runbook_id: str | None = None,
    success: bool | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [
        o.model_dump()
        for o in analyzer.list_outcomes(runbook_id=runbook_id, success=success, limit=limit)
    ]


@router.get("/outcomes/{outcome_id}")
async def get_outcome(
    outcome_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    outcome = analyzer.get_outcome(outcome_id)
    if outcome is None:
        raise HTTPException(404, f"Outcome '{outcome_id}' not found")
    return outcome.model_dump()


@router.post("/effectiveness/{runbook_id}")
async def calculate_effectiveness(
    runbook_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    score = analyzer.calculate_effectiveness(runbook_id)
    return score.model_dump()


@router.get("/decay")
async def detect_runbook_decay(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [s.model_dump() for s in analyzer.detect_runbook_decay()]


@router.get("/failure-patterns")
async def analyze_failure_patterns(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.analyze_failure_patterns()


@router.get("/improvements/{runbook_id}")
async def suggest_improvements(
    runbook_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return analyzer.suggest_improvements(runbook_id)


@router.get("/ranking")
async def rank_runbooks_by_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    analyzer = _get_analyzer()
    return [s.model_dump() for s in analyzer.rank_runbooks_by_effectiveness()]


@router.get("/report")
async def generate_effectiveness_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.generate_effectiveness_report().model_dump()


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    analyzer = _get_analyzer()
    return analyzer.get_stats()
