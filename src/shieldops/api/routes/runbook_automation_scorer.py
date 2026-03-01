"""Runbook Automation Scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.runbook_automation_scorer import (
    AutomationBarrier,
    AutomationBenefit,
    AutomationLevel,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/runbook-automation-scorer",
    tags=["Runbook Automation Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Runbook automation scorer service unavailable")
    return _engine


class RecordAutomationRequest(BaseModel):
    runbook_id: str
    automation_level: AutomationLevel = AutomationLevel.FULLY_MANUAL
    automation_barrier: AutomationBarrier = AutomationBarrier.COMPLEXITY
    automation_benefit: AutomationBenefit = AutomationBenefit.TIME_SAVINGS
    automation_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddMetricRequest(BaseModel):
    runbook_id: str
    automation_level: AutomationLevel = AutomationLevel.FULLY_MANUAL
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/automations")
async def record_automation(
    body: RecordAutomationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_automation(**body.model_dump())
    return result.model_dump()


@router.get("/automations")
async def list_automations(
    automation_level: AutomationLevel | None = None,
    automation_barrier: AutomationBarrier | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_automations(
            automation_level=automation_level,
            automation_barrier=automation_barrier,
            team=team,
            limit=limit,
        )
    ]


@router.get("/automations/{record_id}")
async def get_automation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_automation(record_id)
    if result is None:
        raise HTTPException(404, f"Automation '{record_id}' not found")
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
async def analyze_automation_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_automation_distribution()


@router.get("/manual-runbooks")
async def identify_manual_runbooks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_manual_runbooks()


@router.get("/automation-rankings")
async def rank_by_automation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_automation()


@router.get("/trends")
async def detect_automation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_automation_trends()


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


rax_route = router
