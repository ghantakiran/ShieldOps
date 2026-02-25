"""Spot Instance Manager — manage spot/preemptible instance lifecycle."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class InstanceStatus(StrEnum):
    RUNNING = "running"
    INTERRUPTED = "interrupted"
    MIGRATING = "migrating"
    TERMINATED = "terminated"
    PENDING = "pending"


class FallbackStrategy(StrEnum):
    ON_DEMAND = "on_demand"
    DIFFERENT_AZ = "different_az"
    DIFFERENT_TYPE = "different_type"
    SCALE_DOWN = "scale_down"
    QUEUE_WORK = "queue_work"


class SpotMarket(StrEnum):
    AWS_SPOT = "aws_spot"
    GCP_PREEMPTIBLE = "gcp_preemptible"
    AZURE_SPOT = "azure_spot"
    AWS_SPOT_FLEET = "aws_spot_fleet"
    GCP_SPOT = "gcp_spot"


# --- Models ---


class SpotInstance(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    instance_id: str = ""
    instance_type: str = ""
    market: SpotMarket = SpotMarket.AWS_SPOT
    status: InstanceStatus = InstanceStatus.PENDING
    hourly_rate: float = 0.0
    on_demand_rate: float = 0.0
    savings_pct: float = 0.0
    fallback_strategy: FallbackStrategy = FallbackStrategy.ON_DEMAND
    launched_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class InterruptionEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    spot_id: str = ""
    reason: str = ""
    warning_seconds: int = 0
    fallback_used: FallbackStrategy = FallbackStrategy.ON_DEMAND
    recovery_success: bool = False
    occurred_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class SpotReport(BaseModel):
    total_instances: int = 0
    total_interruptions: int = 0
    interruption_rate_pct: float = 0.0
    total_savings: float = 0.0
    avg_savings_pct: float = 0.0
    by_market: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SpotInstanceManager:
    """Manage spot/preemptible instance lifecycle."""

    def __init__(
        self,
        max_instances: int = 100000,
        min_savings_pct: float = 30.0,
    ) -> None:
        self._max_instances = max_instances
        self._min_savings_pct = min_savings_pct
        self._items: list[SpotInstance] = []
        self._interruptions: list[InterruptionEvent] = []
        logger.info(
            "spot_instance_manager.initialized",
            max_instances=max_instances,
            min_savings_pct=min_savings_pct,
        )

    def register_instance(
        self,
        instance_id: str,
        instance_type: str,
        market: SpotMarket,
        hourly_rate: float,
        on_demand_rate: float,
        fallback_strategy: FallbackStrategy = (FallbackStrategy.ON_DEMAND),
        **kw: Any,
    ) -> SpotInstance:
        """Register a new spot instance."""
        savings_pct = 0.0
        if on_demand_rate > 0:
            savings_pct = round(
                (on_demand_rate - hourly_rate) / on_demand_rate * 100,
                2,
            )

        instance = SpotInstance(
            instance_id=instance_id,
            instance_type=instance_type,
            market=market,
            status=InstanceStatus.RUNNING,
            hourly_rate=hourly_rate,
            on_demand_rate=on_demand_rate,
            savings_pct=savings_pct,
            fallback_strategy=fallback_strategy,
            **kw,
        )
        self._items.append(instance)
        if len(self._items) > self._max_instances:
            self._items = self._items[-self._max_instances :]
        logger.info(
            "spot_instance_manager.instance_registered",
            spot_id=instance.id,
            instance_id=instance_id,
            market=market,
            savings_pct=savings_pct,
        )
        return instance

    def get_instance(
        self,
        spot_id: str,
    ) -> SpotInstance | None:
        """Retrieve a single instance by internal ID."""
        for inst in self._items:
            if inst.id == spot_id:
                return inst
        return None

    def list_instances(
        self,
        market: SpotMarket | None = None,
        status: InstanceStatus | None = None,
        limit: int = 50,
    ) -> list[SpotInstance]:
        """List instances with optional filtering."""
        results = list(self._items)
        if market is not None:
            results = [i for i in results if i.market == market]
        if status is not None:
            results = [i for i in results if i.status == status]
        return results[-limit:]

    def record_interruption(
        self,
        spot_id: str,
        reason: str,
        warning_seconds: int,
    ) -> InterruptionEvent | None:
        """Record a spot interruption event."""
        instance = self.get_instance(spot_id)
        if instance is None:
            return None

        instance.status = InstanceStatus.INTERRUPTED

        event = InterruptionEvent(
            spot_id=spot_id,
            reason=reason,
            warning_seconds=warning_seconds,
            fallback_used=instance.fallback_strategy,
        )
        self._interruptions.append(event)
        if len(self._interruptions) > self._max_instances:
            self._interruptions = self._interruptions[-self._max_instances :]
        logger.info(
            "spot_instance_manager.interruption_recorded",
            spot_id=spot_id,
            reason=reason,
            warning_seconds=warning_seconds,
        )
        return event

    def execute_fallback(
        self,
        spot_id: str,
        strategy: FallbackStrategy,
    ) -> SpotInstance | None:
        """Execute a fallback strategy for a spot instance."""
        instance = self.get_instance(spot_id)
        if instance is None:
            return None

        instance.fallback_strategy = strategy
        instance.status = InstanceStatus.MIGRATING

        # Mark interruption as recovered
        for evt in reversed(self._interruptions):
            if evt.spot_id == spot_id and not evt.recovery_success:
                evt.recovery_success = True
                evt.fallback_used = strategy
                break

        logger.info(
            "spot_instance_manager.fallback_executed",
            spot_id=spot_id,
            strategy=strategy,
        )
        return instance

    def calculate_savings(self) -> dict[str, Any]:
        """Calculate total and per-market savings."""
        total_savings = 0.0
        market_savings: dict[str, float] = {}
        for inst in self._items:
            saving = inst.on_demand_rate - inst.hourly_rate
            total_savings += max(0.0, saving)
            key = inst.market.value
            market_savings[key] = market_savings.get(key, 0.0) + max(0.0, saving)
        return {
            "total_hourly_savings": round(total_savings, 2),
            "instance_count": len(self._items),
            "by_market": {k: round(v, 2) for k, v in market_savings.items()},
        }

    def predict_interruption_risk(
        self,
        instance_type: str,
    ) -> dict[str, Any]:
        """Predict interruption risk based on history."""
        type_instances = [i for i in self._items if i.instance_type == instance_type]
        type_interruptions = [
            e
            for e in self._interruptions
            if any(i.instance_type == instance_type and i.id == e.spot_id for i in self._items)
        ]
        total = len(type_instances)
        interrupted = len(type_interruptions)
        rate = round(interrupted / total * 100, 2) if total else 0.0

        risk = "low"
        if rate > 30:
            risk = "high"
        elif rate > 15:
            risk = "medium"

        return {
            "instance_type": instance_type,
            "total_instances": total,
            "total_interruptions": interrupted,
            "interruption_rate_pct": rate,
            "risk_level": risk,
        }

    def identify_optimal_markets(
        self,
    ) -> list[dict[str, Any]]:
        """Rank markets by savings and reliability."""
        market_data: dict[str, dict[str, Any]] = {}
        for inst in self._items:
            key = inst.market.value
            if key not in market_data:
                market_data[key] = {
                    "market": key,
                    "instance_count": 0,
                    "avg_savings_pct": 0.0,
                    "interruption_count": 0,
                }
            market_data[key]["instance_count"] += 1

        for key, entry in market_data.items():
            instances = [i for i in self._items if i.market.value == key]
            if instances:
                avg = sum(i.savings_pct for i in instances) / len(instances)
                entry["avg_savings_pct"] = round(avg, 2)
            interrupts = [
                e
                for e in self._interruptions
                if any(i.market.value == key and i.id == e.spot_id for i in self._items)
            ]
            entry["interruption_count"] = len(interrupts)

        ranked = sorted(
            market_data.values(),
            key=lambda x: x["avg_savings_pct"],
            reverse=True,
        )
        return ranked

    def generate_spot_report(self) -> SpotReport:
        """Generate a comprehensive spot instance report."""
        total = len(self._items)
        total_int = len(self._interruptions)
        int_rate = round(total_int / total * 100, 2) if total else 0.0

        savings_data = self.calculate_savings()
        avg_sav = 0.0
        if self._items:
            avg_sav = round(
                sum(i.savings_pct for i in self._items) / len(self._items),
                2,
            )

        by_market: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for i in self._items:
            by_market[i.market.value] = by_market.get(i.market.value, 0) + 1
            by_status[i.status.value] = by_status.get(i.status.value, 0) + 1

        by_strategy: dict[str, int] = {}
        for e in self._interruptions:
            by_strategy[e.fallback_used.value] = by_strategy.get(e.fallback_used.value, 0) + 1

        recommendations: list[str] = []
        if int_rate > 20:
            recommendations.append(
                f"Interruption rate {int_rate:.1f}% is high — diversify across AZs and types"
            )
        low_sav = [i for i in self._items if i.savings_pct < self._min_savings_pct]
        if low_sav:
            recommendations.append(
                f"{len(low_sav)} instance(s) below"
                f" {self._min_savings_pct}% savings"
                " — consider on-demand instead"
            )
        optimal = self.identify_optimal_markets()
        if optimal:
            recommendations.append(
                f"Best market: {optimal[0]['market']}"
                f" ({optimal[0]['avg_savings_pct']}%"
                " avg savings)"
            )

        report = SpotReport(
            total_instances=total,
            total_interruptions=total_int,
            interruption_rate_pct=int_rate,
            total_savings=savings_data["total_hourly_savings"],
            avg_savings_pct=avg_sav,
            by_market=by_market,
            by_status=by_status,
            by_strategy=by_strategy,
            recommendations=recommendations,
        )
        logger.info(
            "spot_instance_manager.report_generated",
            total_instances=total,
            total_interruptions=total_int,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored instances and interruptions."""
        self._items.clear()
        self._interruptions.clear()
        logger.info("spot_instance_manager.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        market_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for i in self._items:
            market_counts[i.market.value] = market_counts.get(i.market.value, 0) + 1
            status_counts[i.status.value] = status_counts.get(i.status.value, 0) + 1
        return {
            "total_instances": len(self._items),
            "total_interruptions": len(self._interruptions),
            "market_distribution": market_counts,
            "status_distribution": status_counts,
            "max_instances": self._max_instances,
            "min_savings_pct": self._min_savings_pct,
        }
