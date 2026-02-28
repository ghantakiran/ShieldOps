"""SLO aggregation dashboard API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.sla.slo_aggregator import (
    AggregationLevel,
    AggregationWindow,
    ComplianceStatus,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/slo-aggregator",
    tags=["SLO Aggregator"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "SLO aggregator service unavailable")
    return _engine


class RecordAggregationRequest(BaseModel):
    service_name: str
    level: AggregationLevel = AggregationLevel.PLATFORM
    status: ComplianceStatus = ComplianceStatus.COMPLIANT
    window: AggregationWindow = AggregationWindow.HOURLY
    compliance_pct: float = 0.0
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    level: AggregationLevel = AggregationLevel.SERVICE
    status: ComplianceStatus = ComplianceStatus.COMPLIANT
    target_compliance_pct: float = 99.9
    evaluation_window_hours: float = 24.0


@router.post("/aggregations")
async def record_aggregation(
    body: RecordAggregationRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_aggregation(**body.model_dump())
    return result.model_dump()


@router.get("/aggregations")
async def list_aggregations(
    service_name: str | None = None,
    level: AggregationLevel | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_aggregations(service_name=service_name, level=level, limit=limit)
    ]


@router.get("/aggregations/{record_id}")
async def get_aggregation(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_aggregation(record_id)
    if result is None:
        raise HTTPException(404, f"Aggregation '{record_id}' not found")
    return result.model_dump()


@router.post("/rules")
async def add_rule(
    body: AddRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_rule(**body.model_dump())
    return result.model_dump()


@router.get("/compliance/{service_name}")
async def analyze_compliance_status(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_compliance_status(service_name)


@router.get("/at-risk")
async def identify_at_risk_slos(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_at_risk_slos()


@router.get("/rankings")
async def rank_by_compliance_rate(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_compliance_rate()


@router.get("/compliance-trends")
async def detect_compliance_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_compliance_trends()


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


sad_route = router
