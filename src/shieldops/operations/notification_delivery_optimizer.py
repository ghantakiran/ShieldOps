"""Notification Delivery Optimizer
optimize delivery timing, plan notification batching,
evaluate delivery reliability."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DeliveryPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BatchStrategy(StrEnum):
    IMMEDIATE = "immediate"
    DIGEST = "digest"
    SCHEDULED = "scheduled"
    ADAPTIVE = "adaptive"


class ReliabilityLevel(StrEnum):
    GUARANTEED = "guaranteed"
    HIGH = "high"
    BEST_EFFORT = "best_effort"
    DEGRADED = "degraded"


# --- Models ---


class NotificationDeliveryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    notification_id: str = ""
    delivery_priority: DeliveryPriority = DeliveryPriority.MEDIUM
    batch_strategy: BatchStrategy = BatchStrategy.IMMEDIATE
    reliability_level: ReliabilityLevel = ReliabilityLevel.HIGH
    delivery_time_ms: float = 0.0
    batch_size: int = 1
    success: bool = True
    channel: str = ""
    created_at: float = Field(default_factory=time.time)


class NotificationDeliveryAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    notification_id: str = ""
    delivery_priority: DeliveryPriority = DeliveryPriority.MEDIUM
    delivery_score: float = 0.0
    avg_delivery_ms: float = 0.0
    success_rate: float = 0.0
    batch_efficiency: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class NotificationDeliveryReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_delivery_time: float = 0.0
    by_delivery_priority: dict[str, int] = Field(default_factory=dict)
    by_batch_strategy: dict[str, int] = Field(default_factory=dict)
    by_reliability_level: dict[str, int] = Field(default_factory=dict)
    slow_channels: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class NotificationDeliveryOptimizer:
    """Optimize delivery timing, plan notification
    batching, evaluate delivery reliability."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[NotificationDeliveryRecord] = []
        self._analyses: dict[str, NotificationDeliveryAnalysis] = {}
        logger.info(
            "notification_delivery_optimizer.init",
            max_records=max_records,
        )

    def record_item(
        self,
        notification_id: str = "",
        delivery_priority: DeliveryPriority = (DeliveryPriority.MEDIUM),
        batch_strategy: BatchStrategy = (BatchStrategy.IMMEDIATE),
        reliability_level: ReliabilityLevel = (ReliabilityLevel.HIGH),
        delivery_time_ms: float = 0.0,
        batch_size: int = 1,
        success: bool = True,
        channel: str = "",
    ) -> NotificationDeliveryRecord:
        record = NotificationDeliveryRecord(
            notification_id=notification_id,
            delivery_priority=delivery_priority,
            batch_strategy=batch_strategy,
            reliability_level=reliability_level,
            delivery_time_ms=delivery_time_ms,
            batch_size=batch_size,
            success=success,
            channel=channel,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "notification_delivery.record_added",
            record_id=record.id,
            notification_id=notification_id,
        )
        return record

    def process(self, key: str) -> NotificationDeliveryAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.channel == rec.channel]
        count = len(related)
        avg_dt = sum(r.delivery_time_ms for r in related) / count if count else 0.0
        succ_rate = sum(1 for r in related if r.success) / count if count else 0.0
        batch_eff = sum(r.batch_size for r in related) / count if count else 0.0
        score = succ_rate * 60 + max(0, 40 - avg_dt / 100)
        analysis = NotificationDeliveryAnalysis(
            notification_id=rec.notification_id,
            delivery_priority=rec.delivery_priority,
            delivery_score=round(score, 2),
            avg_delivery_ms=round(avg_dt, 2),
            success_rate=round(succ_rate, 2),
            batch_efficiency=round(batch_eff, 2),
            description=(f"Notification {rec.notification_id} score {score:.2f}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> NotificationDeliveryReport:
        by_dp: dict[str, int] = {}
        by_bs: dict[str, int] = {}
        by_rl: dict[str, int] = {}
        times: list[float] = []
        for r in self._records:
            k = r.delivery_priority.value
            by_dp[k] = by_dp.get(k, 0) + 1
            k2 = r.batch_strategy.value
            by_bs[k2] = by_bs.get(k2, 0) + 1
            k3 = r.reliability_level.value
            by_rl[k3] = by_rl.get(k3, 0) + 1
            times.append(r.delivery_time_ms)
        avg = round(sum(times) / len(times), 2) if times else 0.0
        ch_times: dict[str, list[float]] = {}
        for r in self._records:
            ch_times.setdefault(r.channel, []).append(r.delivery_time_ms)
        slow = [ch for ch, ts in ch_times.items() if sum(ts) / len(ts) > 1000][:10]
        recs: list[str] = []
        if slow:
            recs.append(f"{len(slow)} slow channels found")
        if not recs:
            recs.append("Delivery performance adequate")
        return NotificationDeliveryReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_delivery_time=avg,
            by_delivery_priority=by_dp,
            by_batch_strategy=by_bs,
            by_reliability_level=by_rl,
            slow_channels=slow,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dp_dist: dict[str, int] = {}
        for r in self._records:
            k = r.delivery_priority.value
            dp_dist[k] = dp_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "priority_distribution": dp_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("notification_delivery_optimizer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def optimize_delivery_timing(
        self,
    ) -> list[dict[str, Any]]:
        """Optimize delivery timing per channel."""
        ch_data: dict[str, list[float]] = {}
        ch_success: dict[str, list[bool]] = {}
        for r in self._records:
            ch_data.setdefault(r.channel, []).append(r.delivery_time_ms)
            ch_success.setdefault(r.channel, []).append(r.success)
        results: list[dict[str, Any]] = []
        for ch, times in ch_data.items():
            avg = sum(times) / len(times) if times else 0.0
            succs = ch_success[ch]
            rate = sum(1 for s in succs if s) / len(succs) if succs else 0.0
            results.append(
                {
                    "channel": ch,
                    "avg_delivery_ms": round(avg, 2),
                    "success_rate": round(rate, 2),
                    "notification_count": len(times),
                    "optimization": "reduce_batch" if avg > 1000 else "maintain",
                }
            )
        results.sort(
            key=lambda x: x["avg_delivery_ms"],
        )
        return results

    def plan_notification_batching(
        self,
    ) -> list[dict[str, Any]]:
        """Plan notification batching strategy."""
        strat_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            s = r.batch_strategy.value
            if s not in strat_data:
                strat_data[s] = {
                    "times": [],
                    "sizes": [],
                    "successes": 0,
                    "total": 0,
                }
            strat_data[s]["times"].append(r.delivery_time_ms)
            strat_data[s]["sizes"].append(r.batch_size)
            strat_data[s]["total"] += 1
            if r.success:
                strat_data[s]["successes"] += 1
        results: list[dict[str, Any]] = []
        for strat, data in strat_data.items():
            avg_time = sum(data["times"]) / len(data["times"]) if data["times"] else 0.0
            avg_size = sum(data["sizes"]) / len(data["sizes"]) if data["sizes"] else 0.0
            rate = data["successes"] / data["total"] if data["total"] else 0.0
            results.append(
                {
                    "strategy": strat,
                    "avg_delivery_ms": round(avg_time, 2),
                    "avg_batch_size": round(avg_size, 2),
                    "success_rate": round(rate, 2),
                    "total_notifications": (data["total"]),
                }
            )
        results.sort(
            key=lambda x: x["success_rate"],
            reverse=True,
        )
        return results

    def evaluate_delivery_reliability(
        self,
    ) -> list[dict[str, Any]]:
        """Evaluate delivery reliability."""
        ch_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            if r.channel not in ch_data:
                ch_data[r.channel] = {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                }
            ch_data[r.channel]["total"] += 1
            if r.success:
                ch_data[r.channel]["success"] += 1
            else:
                ch_data[r.channel]["failed"] += 1
        results: list[dict[str, Any]] = []
        for ch, data in ch_data.items():
            rate = data["success"] / data["total"] if data["total"] else 0.0
            level = (
                "guaranteed"
                if rate > 0.999
                else "high"
                if rate > 0.99
                else "best_effort"
                if rate > 0.95
                else "degraded"
            )
            results.append(
                {
                    "channel": ch,
                    "total": data["total"],
                    "success": data["success"],
                    "failed": data["failed"],
                    "reliability_rate": round(rate, 4),
                    "reliability_level": level,
                }
            )
        results.sort(
            key=lambda x: x["reliability_rate"],
            reverse=True,
        )
        return results
