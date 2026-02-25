"""Metric root cause analyzer API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.analytics.metric_rca import MetricType
from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/metric-rca",
    tags=["Metric RCA"],
)

_engine: Any = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def _get_engine() -> Any:
    if _engine is None:
        raise HTTPException(
            503,
            "Metric RCA service unavailable",
        )
    return _engine


class RecordAnomalyRequest(BaseModel):
    service: str
    metric_type: MetricType
    baseline_value: float = 0.0
    anomaly_value: float = 0.0


class CorrelateChangesRequest(BaseModel):
    anomaly_id: str
    changes: list[str] | None = None


@router.post("/anomalies")
async def record_anomaly(
    body: RecordAnomalyRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.record_anomaly(**body.model_dump())
    return result.model_dump()


@router.get("/anomalies")
async def list_anomalies(
    service: str | None = None,
    metric_type: MetricType | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return [
        r.model_dump()
        for r in engine.list_anomalies(service=service, metric_type=metric_type, limit=limit)
    ]


@router.get("/anomalies/{anomaly_id}")
async def get_anomaly(
    anomaly_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.get_anomaly(anomaly_id)
    if result is None:
        raise HTTPException(404, f"Anomaly '{anomaly_id}' not found")
    return result.model_dump()


@router.post("/anomalies/{anomaly_id}/analyze")
async def analyze_root_cause(
    anomaly_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.analyze_root_cause(anomaly_id)
    return result.model_dump()


@router.post("/correlate")
async def correlate_with_changes(
    body: CorrelateChangesRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.correlate_with_changes(body.anomaly_id, body.changes)


@router.get("/hypotheses/{anomaly_id}")
async def rank_hypotheses(
    anomaly_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    engine = _get_engine()
    return engine.rank_hypotheses(anomaly_id)


@router.post("/anomalies/{anomaly_id}/resolve")
async def mark_resolved(
    anomaly_id: str,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    engine = _get_engine()
    return engine.mark_resolved(anomaly_id)


@router.get("/cause-trends")
async def get_cause_trends(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, int]:
    engine = _get_engine()
    return engine.get_cause_trends()


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


mrc_route = router
