"""Alert deduplication engine API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.alert_dedup import (
    AlertPriority,
    DedupResult,
    DedupStrategy,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/alert-dedup",
    tags=["Alert Dedup"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Alert deduplication service unavailable",
        )
    return _engine


class RecordDedupRequest(BaseModel):
    alert_name: str
    source: str = ""
    fingerprint: str = ""
    strategy: DedupStrategy = DedupStrategy.EXACT_MATCH
    result: DedupResult = DedupResult.UNIQUE
    priority: AlertPriority = AlertPriority.MEDIUM
    duplicate_count: int = 0
    suppressed: bool = False
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    strategy: DedupStrategy = DedupStrategy.EXACT_MATCH
    time_window_seconds: float = 300.0
    match_fields: list[str] = []
    enabled: bool = True
    description: str = ""


@router.post("/records")
async def record_dedup(
    body: RecordDedupRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_dedup(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_dedups(
    strategy: DedupStrategy | None = None,
    result: DedupResult | None = None,
    priority: AlertPriority | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_dedups(
            strategy=strategy,
            result=result,
            priority=priority,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_dedup(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_dedup(record_id)
    if record is None:
        raise HTTPException(404, f"Dedup record '{record_id}' not found")
    return record.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rule = engine.add_rule(**body.model_dump())
    return rule.model_dump()


@router.get("/effectiveness")
async def analyze_dedup_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_dedup_effectiveness()


@router.get("/high-duplicate-sources")
async def identify_high_duplicate_sources(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_high_duplicate_sources()


@router.get("/rank-by-ratio")
async def rank_by_dedup_ratio(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_dedup_ratio()


@router.get("/trends")
async def detect_dedup_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_dedup_trends()


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


ade_route = router
