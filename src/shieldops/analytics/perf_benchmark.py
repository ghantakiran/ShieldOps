"""Performance Benchmark Tracker — track benchmarks, identify regressions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BenchmarkType(StrEnum):
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_IO = "disk_io"


class BenchmarkResult(StrEnum):
    PASSED = "passed"
    REGRESSED = "regressed"
    IMPROVED = "improved"
    BASELINE = "baseline"
    INCONCLUSIVE = "inconclusive"


class ComparisonScope(StrEnum):
    SERVICE = "service"
    CLUSTER = "cluster"
    REGION = "region"
    GLOBAL = "global"
    HISTORICAL = "historical"


# --- Models ---


class BenchmarkRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    benchmark_type: BenchmarkType = BenchmarkType.LATENCY
    benchmark_result: BenchmarkResult = BenchmarkResult.BASELINE
    comparison_scope: ComparisonScope = ComparisonScope.SERVICE
    measured_value: float = 0.0
    baseline_value: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BenchmarkBaseline(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_pattern: str = ""
    benchmark_type: BenchmarkType = BenchmarkType.LATENCY
    comparison_scope: ComparisonScope = ComparisonScope.SERVICE
    target_value: float = 0.0
    tolerance_pct: float = 10.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BenchmarkReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_baselines: int = 0
    regressions: int = 0
    avg_measured_value: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    regressed_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PerformanceBenchmarkTracker:
    """Track performance benchmarks, identify regressions, detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        max_regression_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_regression_pct = max_regression_pct
        self._records: list[BenchmarkRecord] = []
        self._baselines: list[BenchmarkBaseline] = []
        logger.info(
            "perf_benchmark.initialized",
            max_records=max_records,
            max_regression_pct=max_regression_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_benchmark(
        self,
        service_name: str,
        benchmark_type: BenchmarkType = BenchmarkType.LATENCY,
        benchmark_result: BenchmarkResult = BenchmarkResult.BASELINE,
        comparison_scope: ComparisonScope = ComparisonScope.SERVICE,
        measured_value: float = 0.0,
        baseline_value: float = 0.0,
        team: str = "",
    ) -> BenchmarkRecord:
        record = BenchmarkRecord(
            service_name=service_name,
            benchmark_type=benchmark_type,
            benchmark_result=benchmark_result,
            comparison_scope=comparison_scope,
            measured_value=measured_value,
            baseline_value=baseline_value,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "perf_benchmark.benchmark_recorded",
            record_id=record.id,
            service_name=service_name,
            benchmark_type=benchmark_type.value,
            benchmark_result=benchmark_result.value,
        )
        return record

    def get_benchmark(self, record_id: str) -> BenchmarkRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_benchmarks(
        self,
        benchmark_type: BenchmarkType | None = None,
        benchmark_result: BenchmarkResult | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BenchmarkRecord]:
        results = list(self._records)
        if benchmark_type is not None:
            results = [r for r in results if r.benchmark_type == benchmark_type]
        if benchmark_result is not None:
            results = [r for r in results if r.benchmark_result == benchmark_result]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_baseline(
        self,
        service_pattern: str,
        benchmark_type: BenchmarkType = BenchmarkType.LATENCY,
        comparison_scope: ComparisonScope = ComparisonScope.SERVICE,
        target_value: float = 0.0,
        tolerance_pct: float = 10.0,
        description: str = "",
    ) -> BenchmarkBaseline:
        baseline = BenchmarkBaseline(
            service_pattern=service_pattern,
            benchmark_type=benchmark_type,
            comparison_scope=comparison_scope,
            target_value=target_value,
            tolerance_pct=tolerance_pct,
            description=description,
        )
        self._baselines.append(baseline)
        if len(self._baselines) > self._max_records:
            self._baselines = self._baselines[-self._max_records :]
        logger.info(
            "perf_benchmark.baseline_added",
            service_pattern=service_pattern,
            benchmark_type=benchmark_type.value,
            target_value=target_value,
        )
        return baseline

    # -- domain operations --------------------------------------------------

    def analyze_benchmark_distribution(self) -> dict[str, Any]:
        """Group by benchmark_type; return count and avg measured_value per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.benchmark_type.value
            type_data.setdefault(key, []).append(r.measured_value)
        result: dict[str, Any] = {}
        for btype, values in type_data.items():
            result[btype] = {
                "count": len(values),
                "avg_measured_value": round(sum(values) / len(values), 2),
            }
        return result

    def identify_regressions(self) -> list[dict[str, Any]]:
        """Return records where benchmark_result == REGRESSED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.benchmark_result == BenchmarkResult.REGRESSED:
                results.append(
                    {
                        "record_id": r.id,
                        "service_name": r.service_name,
                        "benchmark_type": r.benchmark_type.value,
                        "measured_value": r.measured_value,
                        "baseline_value": r.baseline_value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_deviation(self) -> list[dict[str, Any]]:
        """Group by team, avg deviation from baseline, sort descending."""
        team_devs: dict[str, list[float]] = {}
        for r in self._records:
            deviation = abs(r.measured_value - r.baseline_value)
            team_devs.setdefault(r.team, []).append(deviation)
        results: list[dict[str, Any]] = []
        for team, devs in team_devs.items():
            results.append(
                {
                    "team": team,
                    "avg_deviation": round(sum(devs) / len(devs), 2),
                    "count": len(devs),
                }
            )
        results.sort(key=lambda x: x["avg_deviation"], reverse=True)
        return results

    def detect_benchmark_trends(self) -> dict[str, Any]:
        """Split-half on measured_value; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [r.measured_value for r in self._records]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> BenchmarkReport:
        by_type: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_type[r.benchmark_type.value] = by_type.get(r.benchmark_type.value, 0) + 1
            by_result[r.benchmark_result.value] = by_result.get(r.benchmark_result.value, 0) + 1
            by_scope[r.comparison_scope.value] = by_scope.get(r.comparison_scope.value, 0) + 1
        regression_count = sum(
            1 for r in self._records if r.benchmark_result == BenchmarkResult.REGRESSED
        )
        avg_measured = (
            round(sum(r.measured_value for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        regressed_svcs = [
            r.service_name for r in self._records if r.benchmark_result == BenchmarkResult.REGRESSED
        ][:5]
        regression_pct = (
            round(regression_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        recs: list[str] = []
        if regression_pct > self._max_regression_pct:
            recs.append(
                f"Regression rate {regression_pct}% exceeds threshold ({self._max_regression_pct}%)"
            )
        if regression_count > 0:
            recs.append(f"{regression_count} regression(s) detected — review benchmarks")
        if not recs:
            recs.append("Performance benchmarks are within acceptable limits")
        return BenchmarkReport(
            total_records=len(self._records),
            total_baselines=len(self._baselines),
            regressions=regression_count,
            avg_measured_value=avg_measured,
            by_type=by_type,
            by_result=by_result,
            by_scope=by_scope,
            regressed_services=regressed_svcs,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._baselines.clear()
        logger.info("perf_benchmark.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.benchmark_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_baselines": len(self._baselines),
            "max_regression_pct": self._max_regression_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service_name for r in self._records}),
        }
