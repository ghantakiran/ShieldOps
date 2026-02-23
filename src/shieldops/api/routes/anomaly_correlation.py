"""Anomaly correlation API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(prefix="/anomaly-correlation", tags=["Anomaly Correlation"])

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(503, "Anomaly correlation service unavailable")
    return _engine


class RecordAnomalyRequest(BaseModel):
    service: str
    anomaly_type: str
    metric_name: str = ""
    value: float = 0.0
    baseline: float = 0.0
    deviation_pct: float = 0.0
    timestamp: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateRuleRequest(BaseModel):
    name: str
    source_service: str
    target_service: str
    max_delay_seconds: float = 300.0
    min_confidence: float = 0.5


class CorrelateRequest(BaseModel):
    time_window_seconds: float | None = None


class ClearAnomaliesRequest(BaseModel):
    before_timestamp: float | None = None


@router.post("/anomalies")
async def record_anomaly(
    body: RecordAnomalyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    anomaly = engine.record_anomaly(**body.model_dump())
    return anomaly.model_dump()


@router.get("/anomalies")
async def list_anomalies(
    service: str | None = None,
    anomaly_type: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        a.model_dump()
        for a in engine.list_anomalies(service=service, anomaly_type=anomaly_type, limit=limit)
    ]


@router.post("/rules")
async def create_rule(
    body: CreateRuleRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    rule = engine.create_rule(**body.model_dump())
    return rule.model_dump()


@router.get("/rules")
async def list_rules(
    enabled_only: bool = False,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [r.model_dump() for r in engine.list_rules(enabled_only=enabled_only)]


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    removed = engine.delete_rule(rule_id)
    if not removed:
        raise HTTPException(404, f"Rule '{rule_id}' not found")
    return {"deleted": True, "rule_id": rule_id}


@router.post("/correlate")
async def correlate(
    body: CorrelateRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [c.model_dump() for c in engine.correlate(**body.model_dump())]


@router.get("/correlations")
async def get_correlations(
    service: str | None = None,
    min_strength: float | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        c.model_dump() for c in engine.get_correlations(service=service, min_strength=min_strength)
    ]


@router.post("/clear")
async def clear_anomalies(
    body: ClearAnomaliesRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    count = engine.clear_anomalies(**body.model_dump())
    return {"cleared": count}


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.get_stats()
