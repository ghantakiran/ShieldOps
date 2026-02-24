"""Queue health API routes."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shieldops.api.auth.dependencies import require_role

logger = structlog.get_logger()
router = APIRouter(
    prefix="/queue-health",
    tags=["Queue Health"],
)

_instance: Any = None


def set_monitor(instance: Any) -> None:
    global _instance
    _instance = instance


def _get_monitor() -> Any:
    if _instance is None:
        raise HTTPException(503, "Queue health service unavailable")
    return _instance


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RecordMetricRequest(BaseModel):
    queue_name: str
    queue_type: str = "KAFKA"
    depth: int = 0
    enqueue_rate: float = 0.0
    dequeue_rate: float = 0.0
    oldest_message_age_seconds: float = 0.0


class ConsumerGroupRequest(BaseModel):
    group_name: str
    queue_name: str
    consumer_count: int = 1
    lag: int = 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/metrics")
async def record_metric(
    body: RecordMetricRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    result = monitor.record_metric(
        queue_name=body.queue_name,
        queue_type=body.queue_type.lower(),
        depth=body.depth,
        enqueue_rate=body.enqueue_rate,
        dequeue_rate=body.dequeue_rate,
        oldest_message_age_seconds=body.oldest_message_age_seconds,
    )
    return result.model_dump()


@router.get("/metrics")
async def list_metrics(
    queue_name: str | None = None,
    queue_type: str | None = None,
    limit: int = 100,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    qt = queue_type.lower() if queue_type is not None else None
    return [
        m.model_dump()
        for m in monitor.list_metrics(
            queue_name=queue_name,
            queue_type=qt,
            limit=limit,
        )
    ]


@router.get("/metrics/{metric_id}")
async def get_metric(
    metric_id: str,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    result = monitor.get_metric(metric_id)
    if result is None:
        raise HTTPException(404, f"Metric '{metric_id}' not found")
    return result.model_dump()


@router.post("/consumer-groups")
async def register_consumer_group(
    body: ConsumerGroupRequest,
    _user: Any = Depends(require_role("operator")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    result = monitor.register_consumer_group(
        group_name=body.group_name,
        queue_name=body.queue_name,
        consumer_count=body.consumer_count,
        lag=body.lag,
    )
    return result.model_dump()


@router.get("/consumer-groups")
async def list_consumer_groups(
    queue_name: str | None = None,
    limit: int = 50,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [
        g.model_dump()
        for g in monitor.list_consumer_groups(
            queue_name=queue_name,
            limit=limit,
        )
    ]


@router.get("/stalled")
async def detect_stalled_queues(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [m.model_dump() for m in monitor.detect_stalled_queues()]


@router.get("/throughput")
async def analyze_throughput(
    queue_name: str | None = None,
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.analyze_throughput(queue_name=queue_name)


@router.get("/health-summary")
async def generate_health_summary(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.generate_health_summary().model_dump()


@router.get("/consumer-lag")
async def detect_consumer_lag(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> list[dict[str, Any]]:
    monitor = _get_monitor()
    return [g.model_dump() for g in monitor.detect_consumer_lag()]


@router.get("/stats")
async def get_stats(
    _user: Any = Depends(require_role("viewer")),  # type: ignore[arg-type]
) -> dict[str, Any]:
    monitor = _get_monitor()
    return monitor.get_stats()
