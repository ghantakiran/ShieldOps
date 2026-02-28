"""Compliance automation scorer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.compliance.automation_scorer import (
    AutomationLevel,
    AutomationPriority,
    ControlCategory,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/automation-scorer",
    tags=["Automation Scorer"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Automation scorer service unavailable")
    return _engine


class RecordScoreRequest(BaseModel):
    control_name: str
    automation_level: AutomationLevel = AutomationLevel.PARTIALLY_AUTOMATED
    category: ControlCategory = ControlCategory.MONITORING
    priority: AutomationPriority = AutomationPriority.MEDIUM
    automation_pct: float = 0.0
    details: str = ""


class AddControlRequest(BaseModel):
    control_name: str
    category: ControlCategory = ControlCategory.MONITORING
    priority: AutomationPriority = AutomationPriority.MEDIUM
    target_pct: float = 0.0
    description: str = ""


@router.post("/scores")
async def record_score(
    body: RecordScoreRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_score(**body.model_dump())
    return result.model_dump()


@router.get("/scores")
async def list_scores(
    category: ControlCategory | None = None,
    automation_level: AutomationLevel | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_scores(
            category=category,
            automation_level=automation_level,
            limit=limit,
        )
    ]


@router.get("/scores/{record_id}")
async def get_score(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_score(record_id)
    if result is None:
        raise HTTPException(404, f"Score record '{record_id}' not found")
    return result.model_dump()


@router.post("/controls")
async def add_control(
    body: AddControlRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_control(**body.model_dump())
    return result.model_dump()


@router.get("/category-analysis/{category}")
async def analyze_automation_by_category(
    category: ControlCategory,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_automation_by_category(category)


@router.get("/manual-controls")
async def identify_manual_controls(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_manual_controls()


@router.get("/rankings")
async def rank_by_automation_level(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_automation_level()


@router.get("/trends")
async def detect_automation_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
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


cas_route = router
