"""Toil Automation Tracker API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.toil_automator import (
    AutomationROI,
    AutomationStatus,
    ToilCategory,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/toil-automator", tags=["Toil Automator"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Toil automator service unavailable")
    return _engine


class RecordToilRequest(BaseModel):
    task_id: str
    toil_category: ToilCategory = ToilCategory.MANUAL_DEPLOYMENT
    automation_status: AutomationStatus = AutomationStatus.NOT_STARTED
    automation_roi: AutomationROI = AutomationROI.LOW
    time_savings: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddProgressRequest(BaseModel):
    task_id: str
    toil_category: ToilCategory = ToilCategory.MANUAL_DEPLOYMENT
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_toil(
    body: RecordToilRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_toil(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_toils(
    category: ToilCategory | None = None,
    status: AutomationStatus | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_toils(
            category=category,
            status=status,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_toil(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_toil(record_id)
    if result is None:
        raise HTTPException(404, f"Toil record '{record_id}' not found")
    return result.model_dump()


@router.post("/progress")
async def add_progress(
    body: AddProgressRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_progress(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_automation_coverage(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_automation_coverage()


@router.get("/manual-tasks")
async def identify_manual_tasks(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_manual_tasks()


@router.get("/score-rankings")
async def rank_by_time_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_time_savings()


@router.get("/gaps")
async def detect_automation_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_automation_gaps()


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


tat_route = router
