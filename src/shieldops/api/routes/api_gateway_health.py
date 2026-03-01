"""API Gateway Health Monitor API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.topology.api_gateway_health import (
    GatewayIssue,
    GatewayMetric,
    GatewayStatus,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api-gateway-health", tags=["API Gateway Health"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "API gateway health service unavailable")
    return _engine


class RecordHealthRequest(BaseModel):
    gateway_id: str
    gateway_metric: GatewayMetric = GatewayMetric.ERROR_RATE
    gateway_status: GatewayStatus = GatewayStatus.HEALTHY
    gateway_issue: GatewayIssue = GatewayIssue.RATE_LIMITING
    error_rate_pct: float = 0.0
    team: str = ""
    model_config = {"extra": "forbid"}


class AddAlertRequest(BaseModel):
    alert_name: str
    gateway_metric: GatewayMetric = GatewayMetric.ERROR_RATE
    error_threshold: float = 0.0
    avg_error_rate: float = 0.0
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
    metric: GatewayMetric | None = None,
    status: GatewayStatus | None = None,
    team: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_health_records(
            metric=metric,
            status=status,
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
        raise HTTPException(404, f"Gateway health record '{record_id}' not found")
    return result.model_dump()


@router.post("/alerts")
async def add_alert(
    body: AddAlertRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_alert(**body.model_dump())
    return result.model_dump()


@router.get("/performance")
async def analyze_gateway_performance(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_gateway_performance()


@router.get("/unhealthy")
async def identify_unhealthy_gateways(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_unhealthy_gateways()


@router.get("/error-rankings")
async def rank_by_error_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_error_rate()


@router.get("/degradation")
async def detect_gateway_degradation(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.detect_gateway_degradation()


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


agh_route = router
