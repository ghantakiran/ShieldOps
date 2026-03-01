"""SLO Health Dashboard API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_health import (
    HealthStatus,
    SLOCategory,
    TrendDirection,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/slo-health", tags=["SLO Health"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SLO health service unavailable")
    return _engine


class RecordHealthRequest(BaseModel):
    service_name: str
    health_status: HealthStatus = HealthStatus.UNKNOWN
    slo_category: SLOCategory = SLOCategory.AVAILABILITY
    trend_direction: TrendDirection = TrendDirection.STABLE
    health_score: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddRuleRequest(BaseModel):
    service_pattern: str
    slo_category: SLOCategory = SLOCategory.AVAILABILITY
    min_score: float = 0.0
    alert_on_breach: bool = True
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_health(
    body: RecordHealthRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_health(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_health_records(
    status: HealthStatus | None = None,
    category: SLOCategory | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_health_records(
            status=status,
            category=category,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_health(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_health(record_id)
    if result is None:
        raise HTTPException(404, f"Health record '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_health_distribution(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_health_distribution()


@router.get("/at-risk")
async def identify_at_risk(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_at_risk()


@router.get("/score-rankings")
async def rank_by_health_score(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_health_score()


@router.get("/trends")
async def detect_health_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_health_trends()


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


shd_route = router
