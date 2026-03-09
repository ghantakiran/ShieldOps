"""Metric Cardinality Governor

Cardinality explosion prevention, label policy enforcement, aggregation
recommendations, and cost impact analysis for metric management.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CardinalityLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXPLOSIVE = "explosive"
    CRITICAL = "critical"


class LabelPolicyAction(StrEnum):
    ALLOW = "allow"
    WARN = "warn"
    DROP = "drop"
    AGGREGATE = "aggregate"
    RATELIMIT = "ratelimit"


class MetricCategory(StrEnum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    INFO = "info"


# --- Models ---


class CardinalityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    metric_category: MetricCategory = MetricCategory.GAUGE
    cardinality_level: CardinalityLevel = CardinalityLevel.LOW
    label_policy_action: LabelPolicyAction = LabelPolicyAction.ALLOW
    series_count: int = 0
    label_count: int = 0
    high_cardinality_labels: list[str] = Field(default_factory=list)
    unique_label_values: dict[str, int] = Field(default_factory=dict)
    estimated_cost_usd: float = 0.0
    ingestion_rate_per_sec: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CardinalityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    cardinality_level: CardinalityLevel = CardinalityLevel.LOW
    current_series: int = 0
    projected_series: int = 0
    reduction_potential_pct: float = 0.0
    cost_savings_usd: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CardinalityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_series: int = 0
    total_cost_usd: float = 0.0
    avg_series_per_metric: float = 0.0
    explosive_metrics: int = 0
    by_cardinality_level: dict[str, int] = Field(default_factory=dict)
    by_metric_category: dict[str, int] = Field(default_factory=dict)
    by_label_policy: dict[str, int] = Field(default_factory=dict)
    top_offenders: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MetricCardinalityGovernor:
    """Metric Cardinality Governor

    Cardinality explosion prevention, label policy enforcement, aggregation
    recommendations, and cost impact.
    """

    def __init__(
        self,
        max_records: int = 200000,
        series_warn_threshold: int = 10000,
        series_critical_threshold: int = 100000,
        cost_per_series_usd: float = 0.001,
    ) -> None:
        self._max_records = max_records
        self._series_warn = series_warn_threshold
        self._series_critical = series_critical_threshold
        self._cost_per_series = cost_per_series_usd
        self._records: list[CardinalityRecord] = []
        self._analyses: list[CardinalityAnalysis] = []
        logger.info(
            "metric_cardinality_governor.initialized",
            max_records=max_records,
            series_warn_threshold=series_warn_threshold,
            series_critical_threshold=series_critical_threshold,
        )

    def add_record(
        self,
        metric_name: str,
        metric_category: MetricCategory = MetricCategory.GAUGE,
        series_count: int = 0,
        label_count: int = 0,
        high_cardinality_labels: list[str] | None = None,
        unique_label_values: dict[str, int] | None = None,
        ingestion_rate_per_sec: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CardinalityRecord:
        if series_count >= self._series_critical:
            level = CardinalityLevel.CRITICAL
            action = LabelPolicyAction.DROP
        elif series_count >= self._series_warn * 5:
            level = CardinalityLevel.EXPLOSIVE
            action = LabelPolicyAction.AGGREGATE
        elif series_count >= self._series_warn:
            level = CardinalityLevel.HIGH
            action = LabelPolicyAction.WARN
        elif series_count >= self._series_warn * 0.5:
            level = CardinalityLevel.MODERATE
            action = LabelPolicyAction.ALLOW
        else:
            level = CardinalityLevel.LOW
            action = LabelPolicyAction.ALLOW
        cost = round(series_count * self._cost_per_series, 4)
        record = CardinalityRecord(
            metric_name=metric_name,
            metric_category=metric_category,
            cardinality_level=level,
            label_policy_action=action,
            series_count=series_count,
            label_count=label_count,
            high_cardinality_labels=high_cardinality_labels or [],
            unique_label_values=unique_label_values or {},
            estimated_cost_usd=cost,
            ingestion_rate_per_sec=ingestion_rate_per_sec,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "metric_cardinality_governor.record_added",
            record_id=record.id,
            metric_name=metric_name,
            series_count=series_count,
            cardinality_level=level.value,
        )
        return record

    def get_record(self, record_id: str) -> CardinalityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        cardinality_level: CardinalityLevel | None = None,
        metric_category: MetricCategory | None = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[CardinalityRecord]:
        results = list(self._records)
        if cardinality_level is not None:
            results = [r for r in results if r.cardinality_level == cardinality_level]
        if metric_category is not None:
            results = [r for r in results if r.metric_category == metric_category]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def identify_top_offenders(self, top_n: int = 10) -> list[dict[str, Any]]:
        metric_series: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.metric_name not in metric_series:
                metric_series[r.metric_name] = {
                    "metric_name": r.metric_name,
                    "max_series": 0,
                    "total_cost": 0.0,
                    "high_card_labels": set(),
                    "services": set(),
                }
            entry = metric_series[r.metric_name]
            entry["max_series"] = max(entry["max_series"], r.series_count)
            entry["total_cost"] += r.estimated_cost_usd
            entry["high_card_labels"].update(r.high_cardinality_labels)
            entry["services"].add(r.service)
        results: list[dict[str, Any]] = []
        for entry in metric_series.values():
            results.append(
                {
                    "metric_name": entry["metric_name"],
                    "max_series": entry["max_series"],
                    "total_cost_usd": round(entry["total_cost"], 4),
                    "high_card_labels": list(entry["high_card_labels"]),
                    "service_count": len(entry["services"]),
                }
            )
        return sorted(results, key=lambda x: x["max_series"], reverse=True)[:top_n]

    def recommend_aggregations(self, metric_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.metric_name == metric_name]
        if not matching:
            return {"metric_name": metric_name, "status": "no_data"}
        latest = matching[-1]
        suggestions: list[dict[str, str]] = []
        for label in latest.high_cardinality_labels:
            unique = latest.unique_label_values.get(label, 0)
            if unique > 100:
                suggestions.append(
                    {
                        "label": label,
                        "action": "drop_or_aggregate",
                        "unique_values": str(unique),
                        "reason": f"Label '{label}' has {unique} unique values",
                    }
                )
            elif unique > 20:
                suggestions.append(
                    {
                        "label": label,
                        "action": "bucket",
                        "unique_values": str(unique),
                        "reason": f"Consider bucketing '{label}' to reduce cardinality",
                    }
                )
        current_cost = latest.estimated_cost_usd
        if suggestions:
            est_reduction = min(0.7, len(suggestions) * 0.15)
            projected_savings = round(current_cost * est_reduction, 4)
        else:
            est_reduction = 0.0
            projected_savings = 0.0
        return {
            "metric_name": metric_name,
            "current_series": latest.series_count,
            "current_cost_usd": current_cost,
            "suggestions": suggestions,
            "estimated_reduction_pct": round(est_reduction * 100, 2),
            "projected_savings_usd": projected_savings,
        }

    def process(self, metric_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.metric_name == metric_name]
        if not matching:
            return {"metric_name": metric_name, "status": "no_data"}
        series_vals = [r.series_count for r in matching]
        costs = [r.estimated_cost_usd for r in matching]
        latest = matching[-1]
        mid = len(series_vals) // 2
        if mid > 0:
            avg_first = sum(series_vals[:mid]) / mid
            avg_second = sum(series_vals[mid:]) / (len(series_vals) - mid)
            growth_rate = round((avg_second - avg_first) / max(1, avg_first) * 100, 2)
        else:
            growth_rate = 0.0
        projected = int(latest.series_count * (1 + growth_rate / 100))
        reduction = round(max(0, 1 - self._series_warn / max(1, projected)) * 100, 2)
        analysis = CardinalityAnalysis(
            metric_name=metric_name,
            cardinality_level=latest.cardinality_level,
            current_series=latest.series_count,
            projected_series=projected,
            reduction_potential_pct=reduction,
            cost_savings_usd=round(reduction / 100 * sum(costs), 4),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return {
            "metric_name": metric_name,
            "record_count": len(matching),
            "current_series": latest.series_count,
            "cardinality_level": latest.cardinality_level.value,
            "growth_rate_pct": growth_rate,
            "projected_series": projected,
            "total_cost_usd": round(sum(costs), 4),
        }

    def generate_report(self) -> CardinalityReport:
        by_level: dict[str, int] = {}
        by_cat: dict[str, int] = {}
        by_policy: dict[str, int] = {}
        for r in self._records:
            by_level[r.cardinality_level.value] = by_level.get(r.cardinality_level.value, 0) + 1
            by_cat[r.metric_category.value] = by_cat.get(r.metric_category.value, 0) + 1
            by_policy[r.label_policy_action.value] = (
                by_policy.get(r.label_policy_action.value, 0) + 1
            )
        total_series = sum(r.series_count for r in self._records)
        total_cost = round(sum(r.estimated_cost_usd for r in self._records), 4)
        unique_metrics = len({r.metric_name for r in self._records})
        avg_series = round(total_series / max(1, unique_metrics), 2)
        explosive = sum(
            1
            for r in self._records
            if r.cardinality_level in (CardinalityLevel.EXPLOSIVE, CardinalityLevel.CRITICAL)
        )
        offenders = self.identify_top_offenders(5)
        recs: list[str] = []
        if explosive > 0:
            recs.append(
                f"{explosive} metric(s) with explosive/critical cardinality — immediate action"
            )
        if total_cost > 100:
            recs.append(f"Total cardinality cost ${total_cost:.2f} — review label policies")
        if offenders:
            top = offenders[0]
            recs.append(f"Top offender: {top['metric_name']} with {top['max_series']} series")
        if not recs:
            recs.append("Metric cardinality is within healthy bounds")
        return CardinalityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_series=total_series,
            total_cost_usd=total_cost,
            avg_series_per_metric=avg_series,
            explosive_metrics=explosive,
            by_cardinality_level=by_level,
            by_metric_category=by_cat,
            by_label_policy=by_policy,
            top_offenders=offenders,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            level_dist[r.cardinality_level.value] = level_dist.get(r.cardinality_level.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "series_warn_threshold": self._series_warn,
            "series_critical_threshold": self._series_critical,
            "cost_per_series_usd": self._cost_per_series,
            "cardinality_distribution": level_dist,
            "unique_metrics": len({r.metric_name for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("metric_cardinality_governor.cleared")
        return {"status": "cleared"}
