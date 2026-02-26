"""Incident auto-triage API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.incidents.auto_triage import (
    TriageCategory,
    TriageConfidence,
    TriagePriority,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/auto-triage",
    tags=["Auto Triage"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Auto-triage service unavailable")
    return _engine


class RecordTriageRequest(BaseModel):
    incident_id: str
    category: TriageCategory = TriageCategory.APPLICATION
    priority: TriagePriority = TriagePriority.P3_MEDIUM
    confidence: TriageConfidence | None = None
    assigned_team: str = ""
    triage_time_seconds: float = 0.0
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    category: TriageCategory = TriageCategory.APPLICATION
    priority: TriagePriority = TriagePriority.P3_MEDIUM
    match_pattern: str = ""
    hit_count: int = 0


@router.post("/triages")
async def record_triage(
    body: RecordTriageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_triage(**body.model_dump())
    return result.model_dump()


@router.get("/triages")
async def list_triages(
    incident_id: str | None = None,
    category: TriageCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_triages(incident_id=incident_id, category=category, limit=limit)
    ]


@router.get("/triages/{record_id}")
async def get_triage(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_triage(record_id)
    if result is None:
        raise HTTPException(404, f"Triage '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/accuracy/{incident_id}")
async def analyze_triage_accuracy(
    incident_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_triage_accuracy(incident_id)


@router.get("/misclassified")
async def identify_misclassified(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_misclassified()


@router.get("/rankings")
async def rank_rules_by_hit_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_rules_by_hit_rate()


@router.get("/category-drift")
async def detect_category_drift(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_category_drift()


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


iat_route = router
