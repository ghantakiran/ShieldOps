"""Operational toil classifier API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.operations.toil_classifier import (
    AutomationPotential,
    ToilCategory,
    ToilImpact,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/toil-classifier",
    tags=["Toil Classifier"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Toil classifier service unavailable",
        )
    return _engine


class RecordToilRequest(BaseModel):
    task_name: str
    category: ToilCategory = ToilCategory.MANUAL_INTERVENTION
    impact: ToilImpact = ToilImpact.MODERATE
    automation_potential: AutomationPotential = AutomationPotential.PARTIALLY_AUTOMATABLE
    hours_per_week: float = 0.0
    details: str = ""


class AddClassificationRequest(BaseModel):
    task_name: str
    category: ToilCategory = ToilCategory.MANUAL_INTERVENTION
    impact: ToilImpact = ToilImpact.MODERATE
    automation_potential: AutomationPotential = AutomationPotential.PARTIALLY_AUTOMATABLE
    estimated_savings_hours: float = 0.0
    details: str = ""


@router.post("/toils")
async def record_toil(
    body: RecordToilRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_toil(**body.model_dump())
    return result.model_dump()


@router.get("/toils")
async def list_toils(
    task_name: str | None = None,
    category: ToilCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_toils(
            task_name=task_name,
            category=category,
            limit=limit,
        )
    ]


@router.get("/toils/{record_id}")
async def get_toil(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_toil(record_id)
    if result is None:
        raise HTTPException(404, f"Toil record '{record_id}' not found")
    return result.model_dump()


@router.post("/classifications")
async def add_classification(
    body: AddClassificationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_classification(**body.model_dump())
    return result.model_dump()


@router.get("/analysis/{task_name}")
async def analyze_toil_by_category(
    task_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_toil_by_category(task_name)


@router.get("/high-impact")
async def identify_high_impact_toil(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_impact_toil()


@router.get("/rankings")
async def rank_by_automation_potential(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_automation_potential()


@router.get("/trends")
async def detect_toil_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_toil_trends()


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


tcl_route = router
