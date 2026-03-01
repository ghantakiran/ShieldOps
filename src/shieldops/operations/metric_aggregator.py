"""Operational Metric Aggregator — aggregate metrics for dashboards."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MetricDomain(StrEnum):
    RELIABILITY = "reliability"
    PERFORMANCE = "performance"
    EFFICIENCY = "efficiency"
    SECURITY = "security"
    COST = "cost"


class AggregationLevel(StrEnum):
    PLATFORM = "platform"
    TEAM = "team"
    SERVICE = "service"
    ENVIRONMENT = "environment"
    COMPONENT = "component"


class MetricTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class MetricRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    domain: MetricDomain = MetricDomain.RELIABILITY
    aggregation_level: AggregationLevel = AggregationLevel.PLATFORM
    value: float = 0.0
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class MetricThreshold(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_pattern: str = ""
    domain: MetricDomain = MetricDomain.RELIABILITY
    aggregation_level: AggregationLevel = AggregationLevel.PLATFORM
    min_value: float = 0.0
    max_value: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class OperationalMetricReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_thresholds: int = 0
    breached_count: int = 0
    avg_metric_value: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    breached_metrics: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class OperationalMetricAggregator:
    """Aggregate operational metrics across teams for dashboards."""

    def __init__(
        self,
        max_records: int = 200000,
        min_metric_health_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_metric_health_pct = min_metric_health_pct
        self._records: list[MetricRecord] = []
        self._thresholds: list[MetricThreshold] = []
        logger.info(
            "metric_aggregator.initialized",
            max_records=max_records,
            min_metric_health_pct=min_metric_health_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_metric(
        self,
        metric_name: str,
        domain: MetricDomain = MetricDomain.RELIABILITY,
        aggregation_level: AggregationLevel = (AggregationLevel.PLATFORM),
        value: float = 0.0,
        team: str = "",
        details: str = "",
    ) -> MetricRecord:
        record = MetricRecord(
            metric_name=metric_name,
            domain=domain,
            aggregation_level=aggregation_level,
            value=value,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "metric_aggregator.metric_recorded",
            record_id=record.id,
            metric_name=metric_name,
            domain=domain.value,
            aggregation_level=aggregation_level.value,
        )
        return record

    def get_metric(self, record_id: str) -> MetricRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_metrics(
        self,
        domain: MetricDomain | None = None,
        aggregation_level: AggregationLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MetricRecord]:
        results = list(self._records)
        if domain is not None:
            results = [r for r in results if r.domain == domain]
        if aggregation_level is not None:
            results = [r for r in results if r.aggregation_level == aggregation_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_threshold(
        self,
        metric_pattern: str,
        domain: MetricDomain = MetricDomain.RELIABILITY,
        aggregation_level: AggregationLevel = (AggregationLevel.PLATFORM),
        min_value: float = 0.0,
        max_value: float = 0.0,
        reason: str = "",
    ) -> MetricThreshold:
        threshold = MetricThreshold(
            metric_pattern=metric_pattern,
            domain=domain,
            aggregation_level=aggregation_level,
            min_value=min_value,
            max_value=max_value,
            reason=reason,
        )
        self._thresholds.append(threshold)
        if len(self._thresholds) > self._max_records:
            self._thresholds = self._thresholds[-self._max_records :]
        logger.info(
            "metric_aggregator.threshold_added",
            metric_pattern=metric_pattern,
            domain=domain.value,
            min_value=min_value,
            max_value=max_value,
        )
        return threshold

    # -- domain operations --------------------------------------------------

    def analyze_metric_health(self) -> dict[str, Any]:
        """Group by domain; return count and avg value."""
        domain_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.domain.value
            domain_data.setdefault(key, []).append(r.value)
        result: dict[str, Any] = {}
        for domain, values in domain_data.items():
            result[domain] = {
                "count": len(values),
                "avg_value": round(sum(values) / len(values), 2),
            }
        return result

    def identify_breached_thresholds(
        self,
    ) -> list[dict[str, Any]]:
        """Return metrics breaching any matching threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            for t in self._thresholds:
                if t.metric_pattern in r.metric_name and (
                    r.value < t.min_value or (t.max_value > 0 and r.value > t.max_value)
                ):
                    results.append(
                        {
                            "record_id": r.id,
                            "metric_name": r.metric_name,
                            "value": r.value,
                            "min_value": t.min_value,
                            "max_value": t.max_value,
                            "domain": r.domain.value,
                            "team": r.team,
                        }
                    )
                    break
        return results

    def rank_by_metric_value(self) -> list[dict[str, Any]]:
        """Group by team, avg value, sort descending."""
        team_values: dict[str, list[float]] = {}
        for r in self._records:
            team_values.setdefault(r.team, []).append(r.value)
        results: list[dict[str, Any]] = []
        for team, values in team_values.items():
            results.append(
                {
                    "team": team,
                    "avg_value": round(sum(values) / len(values), 2),
                    "metric_count": len(values),
                }
            )
        results.sort(key=lambda x: x["avg_value"], reverse=True)
        return results

    def detect_metric_trends(self) -> dict[str, Any]:
        """Split-half comparison on values; delta 5.0."""
        if len(self._records) < 2:
            return {
                "trend": "insufficient_data",
                "delta": 0.0,
            }
        scores = [r.value for r in self._records]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> OperationalMetricReport:
        by_domain: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        for r in self._records:
            by_domain[r.domain.value] = by_domain.get(r.domain.value, 0) + 1
            by_level[r.aggregation_level.value] = by_level.get(r.aggregation_level.value, 0) + 1
        # Populate by_trend using domain-level trends
        health = self.analyze_metric_health()
        for domain_key in health:
            by_trend[domain_key] = by_trend.get(domain_key, 0) + 1
        breached = self.identify_breached_thresholds()
        breached_metrics = [b["metric_name"] for b in breached]
        avg_metric_value = (
            round(
                sum(r.value for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        recs: list[str] = []
        if breached:
            recs.append(f"{len(breached)} metric(s) breached thresholds — investigate immediately")
        low_health = sum(1 for r in self._records if r.value < self._min_metric_health_pct)
        if low_health > 0:
            recs.append(
                f"{low_health} metric(s) below health threshold ({self._min_metric_health_pct}%)"
            )
        if not recs:
            recs.append("Operational metric levels are healthy")
        return OperationalMetricReport(
            total_records=len(self._records),
            total_thresholds=len(self._thresholds),
            breached_count=len(breached),
            avg_metric_value=avg_metric_value,
            by_domain=by_domain,
            by_level=by_level,
            by_trend=by_trend,
            breached_metrics=breached_metrics,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._thresholds.clear()
        logger.info("metric_aggregator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            key = r.domain.value
            domain_dist[key] = domain_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_thresholds": len(self._thresholds),
            "min_metric_health_pct": (self._min_metric_health_pct),
            "domain_distribution": domain_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_metrics": len({r.metric_name for r in self._records}),
        }
