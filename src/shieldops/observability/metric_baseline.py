"""Metric Baseline Manager — baseline establishment, deviation detection, auto-update."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BaselineStrategy(StrEnum):
    STATIC = "static"
    ROLLING_AVERAGE = "rolling_average"
    PERCENTILE = "percentile"
    SEASONAL = "seasonal"
    ADAPTIVE = "adaptive"


class DeviationSeverity(StrEnum):
    NORMAL = "normal"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class MetricType(StrEnum):
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    CPU = "cpu"
    MEMORY = "memory"


# --- Models ---


class MetricBaseline(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    metric_name: str = ""
    metric_type: MetricType = MetricType.LATENCY
    strategy: BaselineStrategy = BaselineStrategy.STATIC
    baseline_value: float = 0.0
    upper_bound: float = 0.0
    lower_bound: float = 0.0
    sample_count: int = 0
    last_updated: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class DeviationEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    baseline_id: str = ""
    metric_value: float = 0.0
    deviation_pct: float = 0.0
    severity: DeviationSeverity = DeviationSeverity.NORMAL
    detected_at: float = Field(default_factory=time.time)


class BaselineReport(BaseModel):
    total_baselines: int = 0
    total_deviations: int = 0
    avg_deviation_pct: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    stale_baselines: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MetricBaselineManager:
    """Establish and manage metric baselines per service,
    detect deviations, auto-update baselines."""

    def __init__(
        self,
        max_baselines: int = 100000,
        deviation_threshold_pct: float = 25.0,
    ) -> None:
        self._max_baselines = max_baselines
        self._deviation_threshold_pct = deviation_threshold_pct
        self._items: list[MetricBaseline] = []
        self._deviations: dict[str, list[DeviationEvent]] = {}
        logger.info(
            "metric_baseline.initialized",
            max_baselines=max_baselines,
            deviation_threshold_pct=deviation_threshold_pct,
        )

    # -- CRUD -------------------------------------------------------

    def create_baseline(
        self,
        service_name: str,
        metric_name: str,
        metric_type: MetricType = MetricType.LATENCY,
        strategy: BaselineStrategy = BaselineStrategy.STATIC,
        baseline_value: float = 0.0,
        upper_bound: float = 0.0,
        lower_bound: float = 0.0,
        **kw: Any,
    ) -> MetricBaseline:
        """Create a new metric baseline."""
        bl = MetricBaseline(
            service_name=service_name,
            metric_name=metric_name,
            metric_type=metric_type,
            strategy=strategy,
            baseline_value=baseline_value,
            upper_bound=upper_bound,
            lower_bound=lower_bound,
            **kw,
        )
        self._items.append(bl)
        if len(self._items) > self._max_baselines:
            self._items = self._items[-self._max_baselines :]
        logger.info(
            "metric_baseline.created",
            baseline_id=bl.id,
            service_name=service_name,
            metric_name=metric_name,
        )
        return bl

    def get_baseline(
        self,
        baseline_id: str,
    ) -> MetricBaseline | None:
        """Retrieve a baseline by ID."""
        for item in self._items:
            if item.id == baseline_id:
                return item
        return None

    def list_baselines(
        self,
        service_name: str | None = None,
        metric_type: MetricType | None = None,
        limit: int = 50,
    ) -> list[MetricBaseline]:
        """List baselines with optional filters."""
        results = list(self._items)
        if service_name is not None:
            results = [b for b in results if b.service_name == service_name]
        if metric_type is not None:
            results = [b for b in results if b.metric_type == metric_type]
        return results[-limit:]

    # -- Domain operations ------------------------------------------

    def record_metric_value(
        self,
        baseline_id: str,
        value: float,
    ) -> DeviationEvent | None:
        """Record a metric value and check for deviation."""
        bl = self.get_baseline(baseline_id)
        if bl is None:
            return None
        bl.sample_count += 1
        bl.last_updated = time.time()
        deviation = self.detect_deviation(baseline_id, value)
        if deviation and deviation.severity != DeviationSeverity.NORMAL:
            self._deviations.setdefault(
                baseline_id,
                [],
            ).append(deviation)
        logger.info(
            "metric_baseline.value_recorded",
            baseline_id=baseline_id,
            value=value,
            sample_count=bl.sample_count,
        )
        return deviation

    def detect_deviation(
        self,
        baseline_id: str,
        value: float,
    ) -> DeviationEvent | None:
        """Detect if a value deviates from the baseline."""
        bl = self.get_baseline(baseline_id)
        if bl is None:
            return None
        if bl.baseline_value == 0:
            return DeviationEvent(
                baseline_id=baseline_id,
                metric_value=value,
                deviation_pct=0.0,
                severity=DeviationSeverity.NORMAL,
            )
        dev_pct = abs((value - bl.baseline_value) / bl.baseline_value) * 100
        severity = self._classify_severity(dev_pct)
        return DeviationEvent(
            baseline_id=baseline_id,
            metric_value=value,
            deviation_pct=round(dev_pct, 2),
            severity=severity,
        )

    def _classify_severity(
        self,
        deviation_pct: float,
    ) -> DeviationSeverity:
        """Classify deviation severity by percentage."""
        threshold = self._deviation_threshold_pct
        if deviation_pct < threshold * 0.5:
            return DeviationSeverity.NORMAL
        if deviation_pct < threshold:
            return DeviationSeverity.MINOR
        if deviation_pct < threshold * 2:
            return DeviationSeverity.MODERATE
        if deviation_pct < threshold * 4:
            return DeviationSeverity.MAJOR
        return DeviationSeverity.CRITICAL

    def auto_update_baseline(
        self,
        baseline_id: str,
    ) -> MetricBaseline | None:
        """Auto-update a baseline using recorded deviations."""
        bl = self.get_baseline(baseline_id)
        if bl is None:
            return None
        devs = self._deviations.get(baseline_id, [])
        if not devs:
            return bl
        values = [d.metric_value for d in devs]
        avg_value = sum(values) / len(values)
        bl.baseline_value = round(
            (bl.baseline_value + avg_value) / 2,
            4,
        )
        spread = max(values) - min(values) if len(values) > 1 else 0
        bl.upper_bound = round(bl.baseline_value + spread, 4)
        bl.lower_bound = round(
            max(0, bl.baseline_value - spread),
            4,
        )
        bl.last_updated = time.time()
        logger.info(
            "metric_baseline.auto_updated",
            baseline_id=baseline_id,
            new_baseline=bl.baseline_value,
        )
        return bl

    def identify_stale_baselines(
        self,
        max_age_hours: int = 168,
    ) -> list[MetricBaseline]:
        """Find baselines not updated within max_age_hours."""
        cutoff = time.time() - (max_age_hours * 3600)
        stale = [b for b in self._items if b.last_updated < cutoff]
        logger.info(
            "metric_baseline.stale_identified",
            stale_count=len(stale),
            max_age_hours=max_age_hours,
        )
        return stale

    def calculate_baseline_accuracy(
        self,
    ) -> list[dict[str, Any]]:
        """Calculate accuracy of each baseline using deviations."""
        results: list[dict[str, Any]] = []
        for bl in self._items:
            devs = self._deviations.get(bl.id, [])
            total = len(devs)
            normal = sum(1 for d in devs if d.severity == DeviationSeverity.NORMAL)
            accuracy = round(normal / total * 100, 2) if total else 100.0
            results.append(
                {
                    "baseline_id": bl.id,
                    "service_name": bl.service_name,
                    "metric_name": bl.metric_name,
                    "total_checks": total,
                    "normal_count": normal,
                    "accuracy_pct": accuracy,
                }
            )
        results.sort(key=lambda r: r["accuracy_pct"])
        return results

    # -- Report / stats --------------------------------------------

    def generate_baseline_report(self) -> BaselineReport:
        """Generate a comprehensive baseline report."""
        total_baselines = len(self._items)
        all_devs: list[DeviationEvent] = []
        for devs in self._deviations.values():
            all_devs.extend(devs)
        total_devs = len(all_devs)

        avg_dev = (
            round(
                sum(d.deviation_pct for d in all_devs) / total_devs,
                2,
            )
            if total_devs
            else 0.0
        )

        by_strategy: dict[str, int] = {}
        for b in self._items:
            key = b.strategy.value
            by_strategy[key] = by_strategy.get(key, 0) + 1

        by_severity: dict[str, int] = {}
        for d in all_devs:
            key = d.severity.value
            by_severity[key] = by_severity.get(key, 0) + 1

        stale = self.identify_stale_baselines()
        stale_ids = [b.id for b in stale]

        recs: list[str] = []
        if stale:
            recs.append(f"{len(stale)} baseline(s) are stale — schedule re-calibration")
        critical = by_severity.get(
            DeviationSeverity.CRITICAL.value,
            0,
        )
        major = by_severity.get(
            DeviationSeverity.MAJOR.value,
            0,
        )
        if critical > 0:
            recs.append(f"{critical} critical deviation(s) detected — investigate immediately")
        if major > 0:
            recs.append(f"{major} major deviation(s) detected — review baseline accuracy")
        if total_baselines > 0 and total_devs == 0:
            recs.append("No deviations recorded — verify metric collection is active")

        return BaselineReport(
            total_baselines=total_baselines,
            total_deviations=total_devs,
            avg_deviation_pct=avg_dev,
            by_strategy=by_strategy,
            by_severity=by_severity,
            stale_baselines=stale_ids,
            recommendations=recs,
        )

    def clear_data(self) -> None:
        """Clear all stored data."""
        self._items.clear()
        self._deviations.clear()
        logger.info("metric_baseline.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        services: set[str] = set()
        strategies: dict[str, int] = {}
        types: dict[str, int] = {}
        total_samples = 0
        for b in self._items:
            services.add(b.service_name)
            strategies[b.strategy.value] = strategies.get(b.strategy.value, 0) + 1
            types[b.metric_type.value] = types.get(b.metric_type.value, 0) + 1
            total_samples += b.sample_count
        total_devs = sum(len(d) for d in self._deviations.values())
        return {
            "total_baselines": len(self._items),
            "unique_services": len(services),
            "total_deviations": total_devs,
            "total_samples": total_samples,
            "strategy_distribution": strategies,
            "type_distribution": types,
        }
