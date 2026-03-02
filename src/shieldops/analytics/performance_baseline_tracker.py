"""Performance Baseline Tracker — track performance baselines, detect high deviations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BaselineMetric(StrEnum):
    LATENCY_P50 = "latency_p50"
    LATENCY_P99 = "latency_p99"
    THROUGHPUT_RPS = "throughput_rps"
    ERROR_RATE = "error_rate"
    RESOURCE_UTILIZATION = "resource_utilization"


class BaselineShift(StrEnum):
    SIGNIFICANT_IMPROVEMENT = "significant_improvement"
    MINOR_IMPROVEMENT = "minor_improvement"
    STABLE = "stable"
    MINOR_DEGRADATION = "minor_degradation"
    SIGNIFICANT_DEGRADATION = "significant_degradation"


class BaselineWindow(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


# --- Models ---


class BaselineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    baseline_metric: BaselineMetric = BaselineMetric.LATENCY_P50
    baseline_shift: BaselineShift = BaselineShift.SIGNIFICANT_IMPROVEMENT
    baseline_window: BaselineWindow = BaselineWindow.HOURLY
    deviation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BaselineComparison(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    baseline_metric: BaselineMetric = BaselineMetric.LATENCY_P50
    comparison_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PerformanceBaselineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_comparisons: int = 0
    high_deviation_count: int = 0
    avg_deviation_score: float = 0.0
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_shift: dict[str, int] = Field(default_factory=dict)
    by_window: dict[str, int] = Field(default_factory=dict)
    top_deviations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PerformanceBaselineTracker:
    """Track performance baselines, detect high deviations, measure baseline shifts."""

    def __init__(
        self,
        max_records: int = 200000,
        deviation_threshold: float = 2.0,
    ) -> None:
        self._max_records = max_records
        self._deviation_threshold = deviation_threshold
        self._records: list[BaselineRecord] = []
        self._comparisons: list[BaselineComparison] = []
        logger.info(
            "performance_baseline_tracker.initialized",
            max_records=max_records,
            deviation_threshold=deviation_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_baseline(
        self,
        service_name: str,
        baseline_metric: BaselineMetric = BaselineMetric.LATENCY_P50,
        baseline_shift: BaselineShift = BaselineShift.SIGNIFICANT_IMPROVEMENT,
        baseline_window: BaselineWindow = BaselineWindow.HOURLY,
        deviation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BaselineRecord:
        record = BaselineRecord(
            service_name=service_name,
            baseline_metric=baseline_metric,
            baseline_shift=baseline_shift,
            baseline_window=baseline_window,
            deviation_score=deviation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "performance_baseline_tracker.baseline_recorded",
            record_id=record.id,
            service_name=service_name,
            baseline_metric=baseline_metric.value,
            baseline_shift=baseline_shift.value,
        )
        return record

    def get_baseline(self, record_id: str) -> BaselineRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_baselines(
        self,
        baseline_metric: BaselineMetric | None = None,
        baseline_shift: BaselineShift | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BaselineRecord]:
        results = list(self._records)
        if baseline_metric is not None:
            results = [r for r in results if r.baseline_metric == baseline_metric]
        if baseline_shift is not None:
            results = [r for r in results if r.baseline_shift == baseline_shift]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_comparison(
        self,
        service_name: str,
        baseline_metric: BaselineMetric = BaselineMetric.LATENCY_P50,
        comparison_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BaselineComparison:
        comparison = BaselineComparison(
            service_name=service_name,
            baseline_metric=baseline_metric,
            comparison_score=comparison_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._comparisons.append(comparison)
        if len(self._comparisons) > self._max_records:
            self._comparisons = self._comparisons[-self._max_records :]
        logger.info(
            "performance_baseline_tracker.comparison_added",
            service_name=service_name,
            baseline_metric=baseline_metric.value,
            comparison_score=comparison_score,
        )
        return comparison

    # -- domain operations --------------------------------------------------

    def analyze_baseline_distribution(self) -> dict[str, Any]:
        """Group by baseline_metric; return count and avg deviation_score."""
        metric_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.baseline_metric.value
            metric_data.setdefault(key, []).append(r.deviation_score)
        result: dict[str, Any] = {}
        for metric, scores in metric_data.items():
            result[metric] = {
                "count": len(scores),
                "avg_deviation_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_deviations(self) -> list[dict[str, Any]]:
        """Return records where deviation_score > deviation_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.deviation_score > self._deviation_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "service_name": r.service_name,
                        "baseline_metric": r.baseline_metric.value,
                        "deviation_score": r.deviation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["deviation_score"], reverse=True)

    def rank_by_deviation(self) -> list[dict[str, Any]]:
        """Group by service, avg deviation_score, sort descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.deviation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_deviation_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_deviation_score"], reverse=True)
        return results

    def detect_baseline_trends(self) -> dict[str, Any]:
        """Split-half comparison on comparison_score; delta threshold 5.0."""
        if len(self._comparisons) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.comparison_score for c in self._comparisons]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
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

    def generate_report(self) -> PerformanceBaselineReport:
        by_metric: dict[str, int] = {}
        by_shift: dict[str, int] = {}
        by_window: dict[str, int] = {}
        for r in self._records:
            by_metric[r.baseline_metric.value] = by_metric.get(r.baseline_metric.value, 0) + 1
            by_shift[r.baseline_shift.value] = by_shift.get(r.baseline_shift.value, 0) + 1
            by_window[r.baseline_window.value] = by_window.get(r.baseline_window.value, 0) + 1
        high_deviation_count = sum(
            1 for r in self._records if r.deviation_score > self._deviation_threshold
        )
        scores = [r.deviation_score for r in self._records]
        avg_deviation_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        dev_list = self.identify_high_deviations()
        top_deviations = [o["service_name"] for o in dev_list[:5]]
        recs: list[str] = []
        if high_deviation_count > 0:
            recs.append(
                f"{high_deviation_count} high-deviation baseline(s) — investigate immediately"
            )
        if self._records and avg_deviation_score > self._deviation_threshold:
            recs.append(
                f"Avg deviation score {avg_deviation_score} exceeds threshold "
                f"({self._deviation_threshold})"
            )
        if not recs:
            recs.append("Performance baseline levels are healthy")
        return PerformanceBaselineReport(
            total_records=len(self._records),
            total_comparisons=len(self._comparisons),
            high_deviation_count=high_deviation_count,
            avg_deviation_score=avg_deviation_score,
            by_metric=by_metric,
            by_shift=by_shift,
            by_window=by_window,
            top_deviations=top_deviations,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._comparisons.clear()
        logger.info("performance_baseline_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        metric_dist: dict[str, int] = {}
        for r in self._records:
            key = r.baseline_metric.value
            metric_dist[key] = metric_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_comparisons": len(self._comparisons),
            "deviation_threshold": self._deviation_threshold,
            "metric_distribution": metric_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
