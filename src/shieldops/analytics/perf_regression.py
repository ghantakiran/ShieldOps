"""Performance Regression Detector — detect post-deployment regressions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RegressionSeverity(StrEnum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class MetricCategory(StrEnum):
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"


class ComparisonMethod(StrEnum):
    MEAN_SHIFT = "mean_shift"
    PERCENTILE_SHIFT = "percentile_shift"
    VARIANCE_CHANGE = "variance_change"
    TREND_BREAK = "trend_break"
    DISTRIBUTION_SHIFT = "distribution_shift"


# --- Models ---


class RegressionTest(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    service_name: str = ""
    deployment_id: str = ""
    metric_category: MetricCategory = MetricCategory.LATENCY
    before_value: float = 0.0
    after_value: float = 0.0
    change_pct: float = 0.0
    severity: RegressionSeverity = RegressionSeverity.NONE
    method: ComparisonMethod = ComparisonMethod.MEAN_SHIFT
    is_significant: bool = False
    created_at: float = Field(default_factory=time.time)


class RegressionBaseline(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    service_name: str = ""
    metric_category: MetricCategory = MetricCategory.LATENCY
    baseline_mean: float = 0.0
    baseline_p95: float = 0.0
    baseline_std: float = 0.0
    sample_count: int = 0
    created_at: float = Field(default_factory=time.time)


class RegressionReport(BaseModel):
    total_tests: int = 0
    regressions_found: int = 0
    regression_rate_pct: float = 0.0
    by_severity: dict[str, int] = Field(
        default_factory=dict,
    )
    by_category: dict[str, int] = Field(
        default_factory=dict,
    )
    by_method: dict[str, int] = Field(
        default_factory=dict,
    )
    top_regressions: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Detector ---


class PerformanceRegressionDetector:
    """Detect performance regressions by comparing
    before/after deployment metrics and identifying
    statistically significant degradations."""

    def __init__(
        self,
        max_tests: int = 200000,
        significance_threshold: float = 0.05,
    ) -> None:
        self._max_tests = max_tests
        self._significance_threshold = significance_threshold
        self._items: list[RegressionTest] = []
        self._baselines: list[RegressionBaseline] = []
        logger.info(
            "perf_regression.initialized",
            max_tests=max_tests,
            significance_threshold=significance_threshold,
        )

    # -- run / get / list --------------------------------------------

    def run_test(
        self,
        service_name: str,
        deployment_id: str = "",
        metric_category: MetricCategory = (MetricCategory.LATENCY),
        before_value: float = 0.0,
        after_value: float = 0.0,
        method: ComparisonMethod = (ComparisonMethod.MEAN_SHIFT),
        **kw: Any,
    ) -> RegressionTest:
        """Run a regression test comparing values."""
        change_pct = 0.0
        if before_value != 0:
            change_pct = round(
                (after_value - before_value) / abs(before_value) * 100,
                2,
            )
        severity = self._classify_severity(
            change_pct,
            metric_category,
        )
        is_sig = abs(change_pct) > (self._significance_threshold * 100)
        test = RegressionTest(
            service_name=service_name,
            deployment_id=deployment_id,
            metric_category=metric_category,
            before_value=before_value,
            after_value=after_value,
            change_pct=change_pct,
            severity=severity,
            method=method,
            is_significant=is_sig,
            **kw,
        )
        self._items.append(test)
        if len(self._items) > self._max_tests:
            self._items = self._items[-self._max_tests :]
        logger.info(
            "perf_regression.test_run",
            test_id=test.id,
            service_name=service_name,
            severity=severity,
        )
        return test

    def get_test(
        self,
        test_id: str,
    ) -> RegressionTest | None:
        """Get a test by ID."""
        for item in self._items:
            if item.id == test_id:
                return item
        return None

    def list_tests(
        self,
        service_name: str | None = None,
        severity: RegressionSeverity | None = None,
        limit: int = 50,
    ) -> list[RegressionTest]:
        """List tests with optional filters."""
        results = list(self._items)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def create_baseline(
        self,
        service_name: str,
        metric_category: MetricCategory = (MetricCategory.LATENCY),
        values: list[float] | None = None,
    ) -> RegressionBaseline:
        """Create a baseline from a list of values."""
        vals = values or []
        n = len(vals)
        mean = round(sum(vals) / n, 4) if n else 0.0
        std = (
            round(
                (sum((v - mean) ** 2 for v in vals) / n) ** 0.5,
                4,
            )
            if n
            else 0.0
        )
        sorted_vals = sorted(vals)
        p95 = round(
            sorted_vals[int(n * 0.95)] if n else 0.0,
            4,
        )
        baseline = RegressionBaseline(
            service_name=service_name,
            metric_category=metric_category,
            baseline_mean=mean,
            baseline_p95=p95,
            baseline_std=std,
            sample_count=n,
        )
        self._baselines.append(baseline)
        logger.info(
            "perf_regression.baseline_created",
            baseline_id=baseline.id,
            service_name=service_name,
        )
        return baseline

    def detect_regression(
        self,
        test_id: str,
    ) -> dict[str, Any] | None:
        """Detect regression for a specific test."""
        test = self.get_test(test_id)
        if test is None:
            return None
        is_regression = test.severity != RegressionSeverity.NONE and test.is_significant
        return {
            "test_id": test_id,
            "is_regression": is_regression,
            "severity": test.severity.value,
            "change_pct": test.change_pct,
            "is_significant": test.is_significant,
        }

    def compare_deployments(
        self,
        deployment_a: str,
        deployment_b: str,
    ) -> list[dict[str, Any]]:
        """Compare two deployments across all tests."""
        tests_a = [t for t in self._items if t.deployment_id == deployment_a]
        tests_b = [t for t in self._items if t.deployment_id == deployment_b]
        comparisons: list[dict[str, Any]] = []
        svc_a = {(t.service_name, t.metric_category): t for t in tests_a}
        svc_b = {(t.service_name, t.metric_category): t for t in tests_b}
        for key in sorted(set(svc_a.keys()) | set(svc_b.keys())):
            ta = svc_a.get(key)
            tb = svc_b.get(key)
            comparisons.append(
                {
                    "service_name": key[0],
                    "metric_category": key[1].value,
                    "deploy_a_value": (ta.after_value if ta else None),
                    "deploy_b_value": (tb.after_value if tb else None),
                }
            )
        return comparisons

    def identify_degrading_services(
        self,
    ) -> list[dict[str, Any]]:
        """Identify services with degrading trends."""
        by_svc: dict[str, list[RegressionTest]] = {}
        for t in self._items:
            by_svc.setdefault(t.service_name, []).append(t)
        degrading: list[dict[str, Any]] = []
        for svc, tests in sorted(by_svc.items()):
            regressions = [
                t for t in tests if t.severity != RegressionSeverity.NONE and t.is_significant
            ]
            if len(regressions) >= 2:
                degrading.append(
                    {
                        "service_name": svc,
                        "total_tests": len(tests),
                        "regression_count": len(regressions),
                        "regression_rate": round(
                            len(regressions) / len(tests) * 100,
                            2,
                        ),
                    }
                )
        degrading.sort(
            key=lambda x: x["regression_rate"],
            reverse=True,
        )
        return degrading

    def calculate_false_positive_rate(
        self,
    ) -> float:
        """Calculate false positive rate."""
        significant = [t for t in self._items if t.is_significant]
        if not significant:
            return 0.0
        false_pos = [t for t in significant if t.severity == RegressionSeverity.NONE]
        return round(len(false_pos) / len(significant) * 100, 2)

    # -- report / stats ----------------------------------------------

    def generate_regression_report(
        self,
    ) -> RegressionReport:
        """Generate a comprehensive regression report."""
        regressions = [
            t for t in self._items if t.severity != RegressionSeverity.NONE and t.is_significant
        ]
        rate = (
            round(
                len(regressions) / len(self._items) * 100,
                2,
            )
            if self._items
            else 0.0
        )
        by_severity: dict[str, int] = {}
        for t in self._items:
            key = t.severity.value
            by_severity[key] = by_severity.get(key, 0) + 1
        by_category: dict[str, int] = {}
        for t in self._items:
            key = t.metric_category.value
            by_category[key] = by_category.get(key, 0) + 1
        by_method: dict[str, int] = {}
        for t in self._items:
            key = t.method.value
            by_method[key] = by_method.get(key, 0) + 1
        top = sorted(
            regressions,
            key=lambda t: abs(t.change_pct),
            reverse=True,
        )[:10]
        top_ids = [t.id for t in top]
        recs = self._build_recommendations(
            by_severity,
            rate,
        )
        return RegressionReport(
            total_tests=len(self._items),
            regressions_found=len(regressions),
            regression_rate_pct=rate,
            by_severity=by_severity,
            by_category=by_category,
            by_method=by_method,
            top_regressions=top_ids,
            recommendations=recs,
        )

    def clear_data(self) -> int:
        """Clear all data. Returns count cleared."""
        count = len(self._items)
        self._items.clear()
        self._baselines.clear()
        logger.info("perf_regression.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        severity_dist: dict[str, int] = {}
        for t in self._items:
            key = t.severity.value
            severity_dist[key] = severity_dist.get(key, 0) + 1
        return {
            "total_tests": len(self._items),
            "total_baselines": len(self._baselines),
            "significance_threshold": (self._significance_threshold),
            "severity_distribution": severity_dist,
        }

    # -- internal helpers --------------------------------------------

    def _classify_severity(
        self,
        change_pct: float,
        category: MetricCategory,
    ) -> RegressionSeverity:
        # For error_rate, even small increases matter
        if category == MetricCategory.ERROR_RATE:
            pct = abs(change_pct)
            if pct >= 50:
                return RegressionSeverity.CRITICAL
            if pct >= 25:
                return RegressionSeverity.MAJOR
            if pct >= 10:
                return RegressionSeverity.MODERATE
            if pct >= 5:
                return RegressionSeverity.MINOR
            return RegressionSeverity.NONE
        pct = abs(change_pct)
        if pct >= 100:
            return RegressionSeverity.CRITICAL
        if pct >= 50:
            return RegressionSeverity.MAJOR
        if pct >= 20:
            return RegressionSeverity.MODERATE
        if pct >= 10:
            return RegressionSeverity.MINOR
        return RegressionSeverity.NONE

    def _build_recommendations(
        self,
        by_severity: dict[str, int],
        rate: float,
    ) -> list[str]:
        recs: list[str] = []
        critical = by_severity.get(RegressionSeverity.CRITICAL.value, 0)
        if critical > 0:
            recs.append(f"{critical} critical regression(s) — rollback recommended")
        if rate > 30:
            recs.append("High regression rate — review CI/CD pipeline quality gates")
        if not recs:
            recs.append("Performance regression rate within acceptable range")
        return recs
