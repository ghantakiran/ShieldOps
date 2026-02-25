"""Resource Exhaustion Forecaster — predict when a resource will be fully exhausted."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResourceType(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK_BANDWIDTH = "network_bandwidth"
    IOPS = "iops"


class ExhaustionUrgency(StrEnum):
    SAFE = "safe"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"
    IMMINENT = "imminent"


class ConsumptionTrend(StrEnum):
    DECLINING = "declining"
    STABLE = "stable"
    GRADUAL_INCREASE = "gradual_increase"
    RAPID_INCREASE = "rapid_increase"
    SPIKE = "spike"


# --- Models ---


class ExhaustionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_type: ResourceType = ResourceType.CPU
    resource_name: str = ""
    current_usage_pct: float = 0.0
    capacity_total: float = 0.0
    consumption_rate_per_hour: float = 0.0
    estimated_exhaustion_hours: float = 0.0
    urgency: ExhaustionUrgency = ExhaustionUrgency.SAFE
    trend: ConsumptionTrend = ConsumptionTrend.STABLE
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ExhaustionThreshold(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_type: ResourceType = ResourceType.CPU
    warning_hours: float = 48.0
    critical_hours: float = 12.0
    imminent_hours: float = 2.0
    created_at: float = Field(default_factory=time.time)


class ExhaustionReport(BaseModel):
    total_resources: int = 0
    at_risk_count: int = 0
    by_urgency: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    avg_hours_to_exhaustion: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResourceExhaustionForecaster:
    """Predict when a resource will be fully exhausted."""

    def __init__(
        self,
        max_records: int = 200000,
        default_critical_hours: float = 12.0,
    ) -> None:
        self._max_records = max_records
        self._default_critical_hours = default_critical_hours
        self._records: list[ExhaustionRecord] = []
        self._thresholds: dict[str, ExhaustionThreshold] = {}
        logger.info(
            "resource_exhaustion.initialized",
            max_records=max_records,
            default_critical_hours=default_critical_hours,
        )

    # -- CRUD --

    def record_usage(
        self,
        resource_id: str,
        resource_type: ResourceType,
        resource_name: str,
        current_usage_pct: float,
        capacity_total: float,
        consumption_rate_per_hour: float,
        team: str = "",
    ) -> ExhaustionRecord:
        hours = self._compute_exhaustion(
            current_usage_pct, capacity_total, consumption_rate_per_hour
        )
        urgency = self._classify_urgency(hours, resource_type)
        record = ExhaustionRecord(
            resource_id=resource_id,
            resource_type=resource_type,
            resource_name=resource_name,
            current_usage_pct=current_usage_pct,
            capacity_total=capacity_total,
            consumption_rate_per_hour=consumption_rate_per_hour,
            estimated_exhaustion_hours=round(hours, 2),
            urgency=urgency,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "resource_exhaustion.recorded",
            record_id=record.id,
            resource_id=resource_id,
            urgency=urgency.value,
            hours=round(hours, 2),
        )
        return record

    def get_record(self, record_id: str) -> ExhaustionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        resource_type: ResourceType | None = None,
        urgency: ExhaustionUrgency | None = None,
        limit: int = 50,
    ) -> list[ExhaustionRecord]:
        results = list(self._records)
        if resource_type is not None:
            results = [r for r in results if r.resource_type == resource_type]
        if urgency is not None:
            results = [r for r in results if r.urgency == urgency]
        return results[-limit:]

    # -- Domain operations --

    def forecast_exhaustion(
        self,
        current_usage_pct: float,
        capacity_total: float,
        consumption_rate_per_hour: float,
    ) -> dict[str, Any]:
        hours = self._compute_exhaustion(
            current_usage_pct, capacity_total, consumption_rate_per_hour
        )
        return {
            "estimated_exhaustion_hours": round(hours, 2),
            "current_usage_pct": current_usage_pct,
            "capacity_total": capacity_total,
            "consumption_rate_per_hour": consumption_rate_per_hour,
            "remaining_capacity": round(capacity_total * (1.0 - current_usage_pct / 100.0), 2),
        }

    def set_threshold(
        self,
        resource_type: ResourceType,
        warning_hours: float,
        critical_hours: float,
        imminent_hours: float,
    ) -> ExhaustionThreshold:
        threshold = ExhaustionThreshold(
            resource_type=resource_type,
            warning_hours=warning_hours,
            critical_hours=critical_hours,
            imminent_hours=imminent_hours,
        )
        self._thresholds[resource_type.value] = threshold
        logger.info(
            "resource_exhaustion.threshold_set",
            resource_type=resource_type.value,
            warning_hours=warning_hours,
            critical_hours=critical_hours,
            imminent_hours=imminent_hours,
        )
        return threshold

    def identify_at_risk_resources(
        self,
        hours_threshold: float = 48.0,
    ) -> list[dict[str, Any]]:
        at_risk: list[dict[str, Any]] = []
        for r in self._records:
            if r.estimated_exhaustion_hours <= hours_threshold:
                at_risk.append(
                    {
                        "resource_id": r.resource_id,
                        "resource_name": r.resource_name,
                        "resource_type": r.resource_type.value,
                        "estimated_exhaustion_hours": r.estimated_exhaustion_hours,
                        "urgency": r.urgency.value,
                        "current_usage_pct": r.current_usage_pct,
                    }
                )
        at_risk.sort(key=lambda x: x["estimated_exhaustion_hours"])
        return at_risk

    def compute_consumption_trend(
        self,
        resource_id: str,
    ) -> dict[str, Any]:
        records = [r for r in self._records if r.resource_id == resource_id]
        if len(records) < 2:
            return {
                "resource_id": resource_id,
                "trend": ConsumptionTrend.STABLE.value,
                "sample_count": len(records),
            }
        rates = [r.consumption_rate_per_hour for r in records]
        first_half = rates[: len(rates) // 2]
        second_half = rates[len(rates) // 2 :]
        avg_first = sum(first_half) / len(first_half) if first_half else 0.0
        avg_second = sum(second_half) / len(second_half) if second_half else 0.0
        if avg_first == 0.0 and avg_second == 0.0:
            trend = ConsumptionTrend.STABLE
        elif avg_second > avg_first * 2.0:
            trend = ConsumptionTrend.SPIKE
        elif avg_second > avg_first * 1.3:
            trend = ConsumptionTrend.RAPID_INCREASE
        elif avg_second > avg_first * 1.05:
            trend = ConsumptionTrend.GRADUAL_INCREASE
        elif avg_second < avg_first * 0.8:
            trend = ConsumptionTrend.DECLINING
        else:
            trend = ConsumptionTrend.STABLE
        # Update trend on the most recent record
        records[-1].trend = trend
        return {
            "resource_id": resource_id,
            "trend": trend.value,
            "avg_rate_first_half": round(avg_first, 4),
            "avg_rate_second_half": round(avg_second, 4),
            "sample_count": len(records),
        }

    def rank_by_urgency(self) -> list[dict[str, Any]]:
        urgency_order = {
            ExhaustionUrgency.IMMINENT: 0,
            ExhaustionUrgency.CRITICAL: 1,
            ExhaustionUrgency.WARNING: 2,
            ExhaustionUrgency.WATCH: 3,
            ExhaustionUrgency.SAFE: 4,
        }
        sorted_records = sorted(
            self._records,
            key=lambda r: (urgency_order.get(r.urgency, 5), r.estimated_exhaustion_hours),
        )
        return [
            {
                "resource_id": r.resource_id,
                "resource_name": r.resource_name,
                "resource_type": r.resource_type.value,
                "urgency": r.urgency.value,
                "estimated_exhaustion_hours": r.estimated_exhaustion_hours,
                "current_usage_pct": r.current_usage_pct,
            }
            for r in sorted_records
        ]

    # -- Report --

    def generate_exhaustion_report(self) -> ExhaustionReport:
        by_urgency: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        for r in self._records:
            by_urgency[r.urgency.value] = by_urgency.get(r.urgency.value, 0) + 1
            by_type[r.resource_type.value] = by_type.get(r.resource_type.value, 0) + 1
            by_trend[r.trend.value] = by_trend.get(r.trend.value, 0) + 1
        total = len(self._records)
        at_risk = sum(
            1
            for r in self._records
            if r.urgency
            in (
                ExhaustionUrgency.IMMINENT,
                ExhaustionUrgency.CRITICAL,
                ExhaustionUrgency.WARNING,
            )
        )
        avg_hours = (
            round(sum(r.estimated_exhaustion_hours for r in self._records) / total, 2)
            if total
            else 0.0
        )
        recs: list[str] = []
        imminent_count = by_urgency.get(ExhaustionUrgency.IMMINENT.value, 0)
        critical_count = by_urgency.get(ExhaustionUrgency.CRITICAL.value, 0)
        if imminent_count > 0:
            recs.append(
                f"{imminent_count} resource(s) facing imminent exhaustion — act immediately"
            )
        if critical_count > 0:
            recs.append(f"{critical_count} resource(s) in critical state — plan capacity expansion")
        if not recs:
            recs.append("All resources within safe exhaustion thresholds")
        return ExhaustionReport(
            total_resources=total,
            at_risk_count=at_risk,
            by_urgency=by_urgency,
            by_type=by_type,
            by_trend=by_trend,
            avg_hours_to_exhaustion=avg_hours,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._thresholds.clear()
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        urgency_dist: dict[str, int] = {}
        for r in self._records:
            key = r.urgency.value
            urgency_dist[key] = urgency_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_thresholds": len(self._thresholds),
            "unique_resources": len({r.resource_id for r in self._records}),
            "urgency_distribution": urgency_dist,
        }

    # -- Internal helpers --

    def _compute_exhaustion(
        self,
        current_usage_pct: float,
        capacity_total: float,
        consumption_rate_per_hour: float,
    ) -> float:
        remaining = capacity_total * (1.0 - current_usage_pct / 100.0)
        if consumption_rate_per_hour <= 0:
            return 99999.0
        return remaining / consumption_rate_per_hour

    def _classify_urgency(
        self,
        hours: float,
        resource_type: ResourceType,
    ) -> ExhaustionUrgency:
        threshold = self._thresholds.get(resource_type.value)
        if threshold is not None:
            imminent_h = threshold.imminent_hours
            critical_h = threshold.critical_hours
            warning_h = threshold.warning_hours
        else:
            imminent_h = 2.0
            critical_h = self._default_critical_hours
            warning_h = 48.0
        if hours <= imminent_h:
            return ExhaustionUrgency.IMMINENT
        if hours <= critical_h:
            return ExhaustionUrgency.CRITICAL
        if hours <= warning_h:
            return ExhaustionUrgency.WARNING
        if hours <= 168.0:
            return ExhaustionUrgency.WATCH
        return ExhaustionUrgency.SAFE
