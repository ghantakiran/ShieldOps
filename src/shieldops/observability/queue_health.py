"""Queue Health Monitor — message queue depth, consumer lag, throughput analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class QueueType(StrEnum):
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    SQS = "sqs"
    REDIS = "redis"
    PUBSUB = "pubsub"
    NATS = "nats"


class QueueHealthStatus(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    STALLED = "stalled"
    UNKNOWN = "unknown"


class ConsumerState(StrEnum):
    ACTIVE = "active"
    LAGGING = "lagging"
    IDLE = "idle"
    DISCONNECTED = "disconnected"


# --- Models ---


class QueueMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    queue_name: str = ""
    queue_type: QueueType = QueueType.KAFKA
    depth: int = 0
    enqueue_rate: float = 0.0
    dequeue_rate: float = 0.0
    oldest_message_age_seconds: float = 0.0
    status: QueueHealthStatus = QueueHealthStatus.UNKNOWN
    created_at: float = Field(default_factory=time.time)


class ConsumerGroup(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_name: str = ""
    queue_name: str = ""
    consumer_count: int = 0
    lag: int = 0
    state: ConsumerState = ConsumerState.ACTIVE
    last_seen: float = Field(default_factory=time.time)


class QueueHealthSummary(BaseModel):
    total_queues: int = 0
    healthy_count: int = 0
    warning_count: int = 0
    critical_count: int = 0
    stalled_count: int = 0
    total_consumer_groups: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class QueueHealthMonitor:
    """Message queue depth, consumer lag, and throughput analysis."""

    def __init__(
        self,
        max_metrics: int = 200000,
        stall_threshold_seconds: int = 300,
    ) -> None:
        self._max_metrics = max_metrics
        self._stall_threshold_seconds = stall_threshold_seconds
        self._metrics: list[QueueMetric] = []
        self._consumer_groups: list[ConsumerGroup] = []
        logger.info(
            "queue_health.initialized",
            max_metrics=max_metrics,
            stall_threshold_seconds=stall_threshold_seconds,
        )

    def record_metric(
        self,
        queue_name: str,
        queue_type: QueueType,
        depth: int,
        enqueue_rate: float = 0.0,
        dequeue_rate: float = 0.0,
        oldest_message_age_seconds: float = 0.0,
    ) -> QueueMetric:
        if oldest_message_age_seconds > self._stall_threshold_seconds:
            status = QueueHealthStatus.STALLED
        elif depth > 10000:
            status = QueueHealthStatus.CRITICAL
        elif depth > 1000:
            status = QueueHealthStatus.WARNING
        else:
            status = QueueHealthStatus.HEALTHY
        metric = QueueMetric(
            queue_name=queue_name,
            queue_type=queue_type,
            depth=depth,
            enqueue_rate=enqueue_rate,
            dequeue_rate=dequeue_rate,
            oldest_message_age_seconds=oldest_message_age_seconds,
            status=status,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_metrics:
            self._metrics = self._metrics[-self._max_metrics :]
        logger.info(
            "queue_health.metric_recorded",
            metric_id=metric.id,
            queue_name=queue_name,
            queue_type=queue_type,
            depth=depth,
            status=status,
        )
        return metric

    def get_metric(self, metric_id: str) -> QueueMetric | None:
        for m in self._metrics:
            if m.id == metric_id:
                return m
        return None

    def list_metrics(
        self,
        queue_name: str | None = None,
        queue_type: QueueType | None = None,
        limit: int = 100,
    ) -> list[QueueMetric]:
        results = list(self._metrics)
        if queue_name is not None:
            results = [m for m in results if m.queue_name == queue_name]
        if queue_type is not None:
            results = [m for m in results if m.queue_type == queue_type]
        return results[-limit:]

    def register_consumer_group(
        self,
        group_name: str,
        queue_name: str,
        consumer_count: int = 1,
        lag: int = 0,
    ) -> ConsumerGroup:
        if consumer_count == 0:
            state = ConsumerState.DISCONNECTED
        elif lag > 1000:
            state = ConsumerState.LAGGING
        elif lag == 0 and consumer_count > 0:
            state = ConsumerState.IDLE
        else:
            state = ConsumerState.ACTIVE
        group = ConsumerGroup(
            group_name=group_name,
            queue_name=queue_name,
            consumer_count=consumer_count,
            lag=lag,
            state=state,
        )
        self._consumer_groups.append(group)
        logger.info(
            "queue_health.consumer_group_registered",
            group_id=group.id,
            group_name=group_name,
            queue_name=queue_name,
            state=state,
        )
        return group

    def list_consumer_groups(
        self,
        queue_name: str | None = None,
        limit: int = 50,
    ) -> list[ConsumerGroup]:
        results = list(self._consumer_groups)
        if queue_name is not None:
            results = [g for g in results if g.queue_name == queue_name]
        return results[-limit:]

    def detect_stalled_queues(self) -> list[QueueMetric]:
        latest_per_queue: dict[str, QueueMetric] = {}
        for m in self._metrics:
            latest_per_queue[m.queue_name] = m
        return [m for m in latest_per_queue.values() if m.status == QueueHealthStatus.STALLED]

    def analyze_throughput(
        self,
        queue_name: str | None = None,
    ) -> dict[str, Any]:
        targets = list(self._metrics)
        if queue_name is not None:
            targets = [m for m in targets if m.queue_name == queue_name]
        per_queue: dict[str, dict[str, Any]] = {}
        for m in targets:
            if m.queue_name not in per_queue:
                per_queue[m.queue_name] = {
                    "count": 0,
                    "total_enqueue_rate": 0.0,
                    "total_dequeue_rate": 0.0,
                    "total_depth": 0,
                }
            stats = per_queue[m.queue_name]
            stats["count"] += 1
            stats["total_enqueue_rate"] += m.enqueue_rate
            stats["total_dequeue_rate"] += m.dequeue_rate
            stats["total_depth"] += m.depth
        result: dict[str, Any] = {}
        for qn, stats in per_queue.items():
            count = stats["count"]
            result[qn] = {
                "avg_enqueue_rate": round(stats["total_enqueue_rate"] / count, 2),
                "avg_dequeue_rate": round(stats["total_dequeue_rate"] / count, 2),
                "avg_depth": round(stats["total_depth"] / count, 2),
                "sample_count": count,
            }
        return result

    def generate_health_summary(self) -> QueueHealthSummary:
        latest_per_queue: dict[str, QueueMetric] = {}
        for m in self._metrics:
            latest_per_queue[m.queue_name] = m
        healthy = sum(1 for m in latest_per_queue.values() if m.status == QueueHealthStatus.HEALTHY)
        warning = sum(1 for m in latest_per_queue.values() if m.status == QueueHealthStatus.WARNING)
        critical = sum(
            1 for m in latest_per_queue.values() if m.status == QueueHealthStatus.CRITICAL
        )
        stalled = sum(1 for m in latest_per_queue.values() if m.status == QueueHealthStatus.STALLED)
        recommendations: list[str] = []
        if stalled > 0:
            recommendations.append(
                f"{stalled} queue(s) stalled — check consumers and downstream services"
            )
        if critical > 0:
            recommendations.append(
                f"{critical} queue(s) at critical depth — scale consumers immediately"
            )
        if warning > 0:
            recommendations.append(f"{warning} queue(s) approaching capacity — monitor closely")
        lagging_groups = [g for g in self._consumer_groups if g.state == ConsumerState.LAGGING]
        if lagging_groups:
            recommendations.append(
                f"{len(lagging_groups)} consumer group(s) lagging — consider adding consumers"
            )
        logger.info(
            "queue_health.summary_generated",
            total_queues=len(latest_per_queue),
            healthy=healthy,
            warning=warning,
            critical=critical,
            stalled=stalled,
        )
        return QueueHealthSummary(
            total_queues=len(latest_per_queue),
            healthy_count=healthy,
            warning_count=warning,
            critical_count=critical,
            stalled_count=stalled,
            total_consumer_groups=len(self._consumer_groups),
            recommendations=recommendations,
        )

    def detect_consumer_lag(self) -> list[ConsumerGroup]:
        return [g for g in self._consumer_groups if g.state == ConsumerState.LAGGING]

    def clear_data(self) -> None:
        self._metrics.clear()
        self._consumer_groups.clear()
        logger.info("queue_health.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        queue_names = {m.queue_name for m in self._metrics}
        return {
            "total_metrics": len(self._metrics),
            "total_consumer_groups": len(self._consumer_groups),
            "unique_queues": len(queue_names),
            "queue_names": sorted(queue_names),
        }
