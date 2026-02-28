"""Retention policy manager API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role
from shieldops.observability.retention_policy import (
    ComplianceRequirement,
    DataCategory,
    RetentionTier,
)

logger = structlog.get_logger()
router = APIRouter(
    prefix="/retention-policy",
    tags=["Retention Policy"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Retention policy service unavailable")
    return _engine


class RecordRetentionRequest(BaseModel):
    service_name: str
    data_category: DataCategory = DataCategory.METRICS
    tier: RetentionTier = RetentionTier.HOT
    compliance: ComplianceRequirement = ComplianceRequirement.INTERNAL
    retention_days: int = 0
    details: str = ""


class AddRuleRequest(BaseModel):
    rule_name: str
    data_category: DataCategory = DataCategory.METRICS
    tier: RetentionTier = RetentionTier.HOT
    max_days: int = 365
    description: str = ""


@router.post("/retentions")
async def record_retention(
    body: RecordRetentionRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_retention(**body.model_dump())
    return result.model_dump()


@router.get("/retentions")
async def list_retentions(
    service_name: str | None = None,
    data_category: DataCategory | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_retentions(
            service_name=service_name, data_category=data_category, limit=limit
        )
    ]


@router.get("/retentions/{record_id}")
async def get_retention(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_retention(record_id)
    if result is None:
        raise HTTPException(404, f"Retention '{record_id}' not found")
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
async def analyze_retention_compliance(
    service_name: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.analyze_retention_compliance(service_name)


@router.get("/violations")
async def identify_retention_violations(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_retention_violations()


@router.get("/rankings")
async def rank_by_retention_days(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_retention_days()


@router.get("/trends")
async def detect_retention_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.detect_retention_trends()


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


rpm_route = router
