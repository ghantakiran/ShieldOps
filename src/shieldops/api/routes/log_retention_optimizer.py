"""Log retention optimizer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.log_retention_optimizer import (
    ComplianceRequirement,
    LogValueLevel,
    RetentionTier,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/log-retention",
    tags=["Log Retention"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Log retention service unavailable")
    return _engine


class RecordLogSourceRequest(BaseModel):
    source: str
    current_tier: RetentionTier = RetentionTier.HOT
    value_level: LogValueLevel = LogValueLevel.MEDIUM
    compliance: ComplianceRequirement = ComplianceRequirement.NONE
    retention_days: int = 90
    daily_volume_gb: float = 0.0
    cost_per_gb_month: float = 0.0
    details: str = ""


class AddPolicyRequest(BaseModel):
    source_pattern: str
    recommended_tier: RetentionTier = RetentionTier.WARM
    recommended_days: int = 90
    compliance: ComplianceRequirement = ComplianceRequirement.NONE
    reason: str = ""


@router.post("/sources")
async def record_log_source(
    body: RecordLogSourceRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_log_source(**body.model_dump())
    return result.model_dump()


@router.get("/sources")
async def list_log_sources(
    source: str | None = None,
    value_level: LogValueLevel | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_log_sources(source=source, value_level=value_level, limit=limit)
    ]


@router.get("/sources/{record_id}")
async def get_log_source(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_log_source(record_id)
    if result is None:
        raise HTTPException(404, f"Log source record '{record_id}' not found")
    return result.model_dump()


@router.post("/policies")
async def add_policy(
    body: AddPolicyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.add_policy(**body.model_dump())
    return result.model_dump()


@router.get("/recommend/{source}")
async def recommend_retention(
    source: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.recommend_retention(source)


@router.get("/over-retained")
async def identify_over_retained(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_over_retained()


@router.get("/cost-savings")
async def calculate_cost_savings(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.calculate_cost_savings()


@router.get("/compliance-gaps")
async def analyze_compliance_gaps(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.analyze_compliance_gaps()


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


lro_route = router
