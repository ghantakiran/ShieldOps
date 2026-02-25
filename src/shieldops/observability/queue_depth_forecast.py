"""Queue Depth Forecaster — predict message queue depth trends and overflow risk."""

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
    PUBSUB = "pubsub"
    REDIS_STREAM = "redis_stream"


class BacklogTrend(StrEnum):
    GROWING = "growing"
    STABLE = "stable"
    SHRINKING = "shrinking"
    OSCILLATING = "oscillating"
    EMPTY = "empty"


class OverflowRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"


# --- Models ---


class QueueDepthRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    queue_name: str = ""
    queue_type: QueueType = QueueType.KAFKA
    current_depth: int = 0
    consumer_count: int = 0
    producer_rate: float = 0.0
    consumer_rate: float = 0.0
    trend: BacklogTrend = BacklogTrend.STABLE
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class QueueForecast(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    queue_name: str = ""
    predicted_depth: int = 0
    overflow_risk: OverflowRisk = OverflowRisk.NONE
    time_to_overflow_minutes: float = 0.0
    recommended_consumers: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class QueueDepthReport(BaseModel):
    total_depths: int = 0
    total_forecasts: int = 0
    avg_depth: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    at_risk_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class QueueDepthForecaster:
    """Predict message queue depth trends and overflow risk."""

    def __init__(
        self,
        max_records: int = 200000,
        overflow_threshold: int = 100000,
    ) -> None:
        self._max_records = max_records
        self._overflow_threshold = overflow_threshold
        self._records: list[QueueDepthRecord] = []
        self._forecasts: list[QueueForecast] = []
        logger.info(
            "queue_depth_forecast.initialized",
            max_records=max_records,
            overflow_threshold=overflow_threshold,
        )

    # -- record / get / list ---------------------------------------------

    def record_depth(
        self,
        queue_name: str,
        queue_type: QueueType = QueueType.KAFKA,
        current_depth: int = 0,
        consumer_count: int = 0,
        producer_rate: float = 0.0,
        consumer_rate: float = 0.0,
        trend: BacklogTrend = BacklogTrend.STABLE,
        details: str = "",
    ) -> QueueDepthRecord:
        record = QueueDepthRecord(
            queue_name=queue_name,
            queue_type=queue_type,
            current_depth=current_depth,
            consumer_count=consumer_count,
            producer_rate=producer_rate,
            consumer_rate=consumer_rate,
            trend=trend,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "queue_depth_forecast.depth_recorded",
            record_id=record.id,
            queue_name=queue_name,
            current_depth=current_depth,
        )
        return record

    def get_depth(self, record_id: str) -> QueueDepthRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_depths(
        self,
        queue_name: str | None = None,
        queue_type: QueueType | None = None,
        limit: int = 50,
    ) -> list[QueueDepthRecord]:
        results = list(self._records)
        if queue_name is not None:
            results = [r for r in results if r.queue_name == queue_name]
        if queue_type is not None:
            results = [r for r in results if r.queue_type == queue_type]
        return results[-limit:]

    def create_forecast(
        self,
        queue_name: str,
        predicted_depth: int = 0,
        overflow_risk: OverflowRisk = OverflowRisk.NONE,
        time_to_overflow_minutes: float = 0.0,
        recommended_consumers: int = 0,
        details: str = "",
    ) -> QueueForecast:
        forecast = QueueForecast(
            queue_name=queue_name,
            predicted_depth=predicted_depth,
            overflow_risk=overflow_risk,
            time_to_overflow_minutes=time_to_overflow_minutes,
            recommended_consumers=recommended_consumers,
            details=details,
        )
        self._forecasts.append(forecast)
        if len(self._forecasts) > self._max_records:
            self._forecasts = self._forecasts[-self._max_records :]
        logger.info(
            "queue_depth_forecast.forecast_created",
            queue_name=queue_name,
            overflow_risk=overflow_risk.value,
            predicted_depth=predicted_depth,
        )
        return forecast

    # -- domain operations -----------------------------------------------

    def analyze_queue_health(self, queue_name: str) -> dict[str, Any]:
        """Analyze health of a specific queue."""
        depths = [r for r in self._records if r.queue_name == queue_name]
        if not depths:
            return {"queue_name": queue_name, "status": "no_data"}
        trend_breakdown: dict[str, int] = {}
        total_depth = 0
        for d in depths:
            key = d.trend.value
            trend_breakdown[key] = trend_breakdown.get(key, 0) + 1
            total_depth += d.current_depth
        avg_depth = round(total_depth / len(depths), 2) if depths else 0.0
        forecasts = [f for f in self._forecasts if f.queue_name == queue_name]
        return {
            "queue_name": queue_name,
            "total_depths": len(depths),
            "total_forecasts": len(forecasts),
            "trend_breakdown": trend_breakdown,
            "avg_depth": avg_depth,
        }

    def identify_at_risk_queues(self) -> list[dict[str, Any]]:
        """Find queues with current_depth > overflow_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.current_depth > self._overflow_threshold:
                results.append(
                    {
                        "id": r.id,
                        "queue_name": r.queue_name,
                        "queue_type": r.queue_type.value,
                        "current_depth": r.current_depth,
                        "threshold": self._overflow_threshold,
                    }
                )
        results.sort(key=lambda x: x["current_depth"], reverse=True)
        return results

    def rank_by_backlog_growth(self) -> list[dict[str, Any]]:
        """Rank queues by backlog growth (producer_rate - consumer_rate)."""
        queue_growth: dict[str, list[float]] = {}
        for r in self._records:
            growth = r.producer_rate - r.consumer_rate
            queue_growth.setdefault(r.queue_name, []).append(growth)
        results: list[dict[str, Any]] = []
        for name, growths in queue_growth.items():
            avg_growth = round(sum(growths) / len(growths), 2) if growths else 0.0
            results.append(
                {
                    "queue_name": name,
                    "avg_growth_rate": avg_growth,
                    "samples": len(growths),
                }
            )
        results.sort(key=lambda x: x["avg_growth_rate"], reverse=True)
        return results

    def estimate_consumer_scaling(self) -> list[dict[str, Any]]:
        """Estimate how many additional consumers each queue needs."""
        queue_latest: dict[str, QueueDepthRecord] = {}
        for r in self._records:
            queue_latest[r.queue_name] = r
        results: list[dict[str, Any]] = []
        for name, rec in queue_latest.items():
            if rec.producer_rate > rec.consumer_rate and rec.consumer_count > 0:
                rate_per_consumer = rec.consumer_rate / rec.consumer_count
                if rate_per_consumer > 0:
                    needed = int((rec.producer_rate / rate_per_consumer) - rec.consumer_count)
                    needed = max(needed, 1)
                else:
                    needed = 1
                results.append(
                    {
                        "queue_name": name,
                        "current_consumers": rec.consumer_count,
                        "additional_consumers_needed": needed,
                        "producer_rate": rec.producer_rate,
                        "consumer_rate": rec.consumer_rate,
                    }
                )
        results.sort(key=lambda x: x["additional_consumers_needed"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> QueueDepthReport:
        by_type: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        total_depth = 0
        for r in self._records:
            by_type[r.queue_type.value] = by_type.get(r.queue_type.value, 0) + 1
            by_trend[r.trend.value] = by_trend.get(r.trend.value, 0) + 1
            total_depth += r.current_depth
        avg_depth = round(total_depth / len(self._records), 2) if self._records else 0.0
        at_risk = len(self.identify_at_risk_queues())
        recs: list[str] = []
        if at_risk > 0:
            recs.append(f"{at_risk} queue(s) at overflow risk")
        scaling = len(self.estimate_consumer_scaling())
        if scaling > 0:
            recs.append(f"{scaling} queue(s) need consumer scaling")
        if not recs:
            recs.append("Queue depth health is good")
        return QueueDepthReport(
            total_depths=len(self._records),
            total_forecasts=len(self._forecasts),
            avg_depth=avg_depth,
            by_type=by_type,
            by_trend=by_trend,
            at_risk_count=at_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._forecasts.clear()
        logger.info("queue_depth_forecast.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.queue_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_depths": len(self._records),
            "total_forecasts": len(self._forecasts),
            "overflow_threshold": self._overflow_threshold,
            "type_distribution": type_dist,
            "unique_queues": len({r.queue_name for r in self._records}),
        }
