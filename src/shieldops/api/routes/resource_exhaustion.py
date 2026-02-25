"""Resource exhaustion API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.resource_exhaustion import (
    ExhaustionUrgency,
    ResourceType,
)
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/resource-exhaustion",
    tags=["Resource Exhaustion"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Resource exhaustion service unavailable",
        )
    return _engine


class RecordUsageRequest(BaseModel):
    resource_id: str
    resource_type: ResourceType
    resource_name: str
    current_usage_pct: float
    capacity_total: float
    consumption_rate_per_hour: float
    team: str = ""


class ForecastRequest(BaseModel):
    current_usage_pct: float
    capacity_total: float
    consumption_rate_per_hour: float


class SetThresholdRequest(BaseModel):
    resource_type: ResourceType
    warning_hours: float = 48.0
    critical_hours: float = 12.0
    imminent_hours: float = 2.0


@router.post("/records")
async def record_usage(
    body: RecordUsageRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.record_usage(**body.model_dump())
    return record.model_dump()


@router.get("/records")
async def list_records(
    resource_type: ResourceType | None = None,
    urgency: ExhaustionUrgency | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_records(
            resource_type=resource_type,
            urgency=urgency,
            limit=limit,
        )
    ]


@router.get("/records/{record_id}")
async def get_record(
    record_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    record = engine.get_record(record_id)
    if record is None:
        raise HTTPException(404, f"Record '{record_id}' not found")
    return record.model_dump()


@router.post("/forecast")
async def forecast_exhaustion(
    body: ForecastRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.forecast_exhaustion(**body.model_dump())


@router.post("/thresholds")
async def set_threshold(
    body: SetThresholdRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    threshold = engine.set_threshold(**body.model_dump())
    return threshold.model_dump()


@router.get("/at-risk")
async def get_at_risk_resources(
    hours_threshold: float = 48.0,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.identify_at_risk_resources(
        hours_threshold=hours_threshold,
    )


@router.get("/trend/{resource_id}")
async def get_consumption_trend(
    resource_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.compute_consumption_trend(resource_id)


@router.get("/rank")
async def rank_by_urgency(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_by_urgency()


@router.get("/report")
async def get_report(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    report = engine.generate_exhaustion_report()
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


rex_route = router
