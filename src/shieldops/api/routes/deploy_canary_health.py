"""Deploy Canary Health Monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.changes.deploy_canary_health import (
    CanaryDecision,
    CanaryHealth,
    CanaryMetricType,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/deploy-canary-health", tags=["Deploy Canary Health"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Deploy canary health service unavailable")
    return _engine


class RecordCanaryRequest(BaseModel):
    deployment_id: str
    canary_metric_type: CanaryMetricType = CanaryMetricType.ERROR_RATE
    canary_health: CanaryHealth = CanaryHealth.HEALTHY
    canary_decision: CanaryDecision = CanaryDecision.PROMOTE
    health_score: float = 0.0
    service: str = ""
    team: str = ""
    model_config = {"extra": "forbid"}


class AddComparisonRequest(BaseModel):
    deployment_id: str
    canary_metric_type: CanaryMetricType = CanaryMetricType.ERROR_RATE
    comparison_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    model_config = {"extra": "forbid"}


@router.post("/records")
async def record_canary(
    body: RecordCanaryRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_canary(**body.model_dump())
    return result.model_dump()


@router.get("/records")
async def list_canaries(
    metric_type: CanaryMetricType | None = None,
    health: CanaryHealth | None = None,
    service: str | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_canaries(
            metric_type=metric_type,
            health=health,
            service=service,
            team=team,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_canary(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_canary(record_id)
    if result is None:
        raise HTTPException(404, f"Canary record '{record_id}' not found")
    return result.model_dump()


@router.post("/comparisons")
async def add_comparison(
    body: AddComparisonRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_comparison(**body.model_dump())
    return result.model_dump()


@router.get("/distribution")
async def analyze_canary_health(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_canary_health()


@router.get("/unhealthy-canaries")
async def identify_unhealthy_canaries(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unhealthy_canaries()


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


dch_route = router
