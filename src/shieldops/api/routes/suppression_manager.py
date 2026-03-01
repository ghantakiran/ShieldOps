"""Alert Suppression Manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.suppression_manager import (
    SuppressionScope,
    SuppressionStatus,
    SuppressionType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/suppression-manager", tags=["Suppression Manager"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Alert suppression service unavailable")
    return _engine


class RecordSuppressionRequest(BaseModel):
    alert_type: str
    suppression_type: SuppressionType = SuppressionType.MAINTENANCE
    scope: SuppressionScope = SuppressionScope.SERVICE
    status: SuppressionStatus = SuppressionStatus.PENDING
    suppressed_count: int = 0
    team: str = ""
    details: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    alert_pattern: str
    suppression_type: SuppressionType = SuppressionType.MAINTENANCE
    scope: SuppressionScope = SuppressionScope.SERVICE
    duration_minutes: float = 0.0
    reason: str = ""
    model_config = {"extra": "forbid"}


@router.post("/suppressions")
async def record_suppression(
    body: RecordSuppressionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_suppression(**body.model_dump())
    return result.model_dump()


@router.get("/suppressions")
async def list_suppressions(
    suppression_type: SuppressionType | None = None,
    scope: SuppressionScope | None = None,
    status: SuppressionStatus | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_suppressions(
            suppression_type=suppression_type, scope=scope, status=status, limit=limit
        )
    ]


@router.get("/suppressions/{record_id}")
async def get_suppression(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_suppression(record_id)
    if result is None:
        raise HTTPException(404, f"Suppression record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/effectiveness")
async def analyze_suppression_effectiveness(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_suppression_effectiveness()


@router.get("/over-suppressed")
async def identify_over_suppressed(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_over_suppressed()


@router.get("/team-rankings")
async def rank_by_suppressed_count(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_suppressed_count()


@router.get("/trends")
async def detect_suppression_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_suppression_trends()


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


asn_route = router
