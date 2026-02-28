"""Security Posture Benchmarker — benchmark security posture against industry standards."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BenchmarkCategory(StrEnum):
    IDENTITY = "identity"
    NETWORK = "network"
    DATA = "data"
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"


class BenchmarkGrade(StrEnum):
    LEADING = "leading"
    ABOVE_AVERAGE = "above_average"
    AVERAGE = "average"
    BELOW_AVERAGE = "below_average"
    LAGGING = "lagging"


class BenchmarkSource(StrEnum):
    INDUSTRY_STANDARD = "industry_standard"
    PEER_GROUP = "peer_group"
    INTERNAL_BASELINE = "internal_baseline"
    REGULATORY = "regulatory"
    BEST_PRACTICE = "best_practice"


# --- Models ---


class BenchmarkRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    service: str = ""
    category: BenchmarkCategory = BenchmarkCategory.INFRASTRUCTURE
    grade: BenchmarkGrade = BenchmarkGrade.AVERAGE
    source: BenchmarkSource = BenchmarkSource.INDUSTRY_STANDARD
    benchmark_score: float = 0.0
    peer_score: float = 0.0
    passing: bool = False
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class BenchmarkComparison(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    comparison_name: str = ""
    category: BenchmarkCategory = BenchmarkCategory.INFRASTRUCTURE
    source: BenchmarkSource = BenchmarkSource.INDUSTRY_STANDARD
    our_score: float = 0.0
    benchmark_score: float = 0.0
    delta: float = 0.0
    service: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PostureBenchmarkReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_comparisons: int = 0
    leading_count: int = 0
    lagging_count: int = 0
    avg_benchmark_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    top_lagging_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityPostureBenchmarker:
    """Benchmark security posture against industry standards and peer groups."""

    def __init__(
        self,
        max_records: int = 200000,
        min_benchmark_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_benchmark_score = min_benchmark_score
        self._records: list[BenchmarkRecord] = []
        self._comparisons: list[BenchmarkComparison] = []
        logger.info(
            "posture_benchmark.initialized",
            max_records=max_records,
            min_benchmark_score=min_benchmark_score,
        )

    # -- CRUD --

    def record_benchmark(
        self,
        service: str,
        category: BenchmarkCategory = BenchmarkCategory.INFRASTRUCTURE,
        grade: BenchmarkGrade = BenchmarkGrade.AVERAGE,
        source: BenchmarkSource = BenchmarkSource.INDUSTRY_STANDARD,
        benchmark_score: float = 0.0,
        peer_score: float = 0.0,
        passing: bool = False,
        details: str = "",
    ) -> BenchmarkRecord:
        record = BenchmarkRecord(
            service=service,
            category=category,
            grade=grade,
            source=source,
            benchmark_score=benchmark_score,
            peer_score=peer_score,
            passing=passing,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "posture_benchmark.recorded",
            record_id=record.id,
            service=service,
            grade=grade.value,
        )
        return record

    def get_benchmark(self, record_id: str) -> BenchmarkRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_benchmarks(
        self,
        category: BenchmarkCategory | None = None,
        grade: BenchmarkGrade | None = None,
        source: BenchmarkSource | None = None,
        limit: int = 50,
    ) -> list[BenchmarkRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.category == category]
        if grade is not None:
            results = [r for r in results if r.grade == grade]
        if source is not None:
            results = [r for r in results if r.source == source]
        return results[-limit:]

    def add_comparison(
        self,
        comparison_name: str,
        category: BenchmarkCategory = BenchmarkCategory.INFRASTRUCTURE,
        source: BenchmarkSource = BenchmarkSource.INDUSTRY_STANDARD,
        our_score: float = 0.0,
        benchmark_score: float = 0.0,
        delta: float = 0.0,
        service: str = "",
        description: str = "",
    ) -> BenchmarkComparison:
        comparison = BenchmarkComparison(
            comparison_name=comparison_name,
            category=category,
            source=source,
            our_score=our_score,
            benchmark_score=benchmark_score,
            delta=delta,
            service=service,
            description=description,
        )
        self._comparisons.append(comparison)
        if len(self._comparisons) > self._max_records:
            self._comparisons = self._comparisons[-self._max_records :]
        logger.info(
            "posture_benchmark.comparison_added",
            comparison_id=comparison.id,
            comparison_name=comparison_name,
            service=service,
        )
        return comparison

    # -- Domain operations --

    def analyze_benchmark_by_category(self) -> dict[str, Any]:
        """Compute benchmark metrics grouped by security category."""
        category_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            cat = r.category.value
            if cat not in category_data:
                category_data[cat] = {"total": 0, "scores": [], "lagging": 0}
            category_data[cat]["total"] += 1
            category_data[cat]["scores"].append(r.benchmark_score)
            if r.grade == BenchmarkGrade.LAGGING:
                category_data[cat]["lagging"] += 1
        breakdown: list[dict[str, Any]] = []
        for cat, data in category_data.items():
            scores = data["scores"]
            avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
            lagging_pct = round(data["lagging"] / data["total"] * 100, 2) if data["total"] else 0.0
            breakdown.append(
                {
                    "category": cat,
                    "total_records": data["total"],
                    "lagging_count": data["lagging"],
                    "lagging_pct": lagging_pct,
                    "avg_benchmark_score": avg_score,
                }
            )
        breakdown.sort(key=lambda x: x["avg_benchmark_score"], reverse=True)
        return {
            "total_categories": len(category_data),
            "breakdown": breakdown,
        }

    def identify_lagging_areas(self) -> list[dict[str, Any]]:
        """Return all records where posture grade is lagging."""
        lagging = [r for r in self._records if r.grade == BenchmarkGrade.LAGGING]
        return [
            {
                "record_id": r.id,
                "service": r.service,
                "category": r.category.value,
                "source": r.source.value,
                "benchmark_score": r.benchmark_score,
                "peer_score": r.peer_score,
            }
            for r in lagging
        ]

    def rank_by_benchmark_score(self) -> list[dict[str, Any]]:
        """Rank services by average benchmark score (ascending — lowest first = most at risk)."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            if not r.service:
                continue
            service_scores.setdefault(r.service, []).append(r.benchmark_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_scores.items():
            avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
            results.append(
                {
                    "service": service,
                    "avg_benchmark_score": avg_score,
                    "assessment_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_benchmark_score"])
        return results

    def detect_benchmark_trends(self) -> dict[str, Any]:
        """Detect whether benchmark scores are improving or worsening over time."""
        if len(self._records) < 4:
            return {"trend": "insufficient_data", "sample_count": len(self._records)}
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def _avg_score(records: list[BenchmarkRecord]) -> float:
            if not records:
                return 0.0
            return round(sum(r.benchmark_score for r in records) / len(records), 2)

        first_score = _avg_score(first_half)
        second_score = _avg_score(second_half)
        delta = round(second_score - first_score, 2)
        if delta > 3.0:
            trend = "improving"
        elif delta < -3.0:
            trend = "worsening"
        else:
            trend = "stable"
        return {
            "trend": trend,
            "first_half_avg_score": first_score,
            "second_half_avg_score": second_score,
            "delta": delta,
            "total_records": len(self._records),
        }

    # -- Report --

    def generate_report(self) -> PostureBenchmarkReport:
        by_category: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
            by_source[r.source.value] = by_source.get(r.source.value, 0) + 1
        total = len(self._records)
        leading_count = by_grade.get(BenchmarkGrade.LEADING.value, 0)
        lagging_count = by_grade.get(BenchmarkGrade.LAGGING.value, 0)
        avg_score = (
            round(sum(r.benchmark_score for r in self._records) / total, 4) if total else 0.0
        )
        lagging_records = self.identify_lagging_areas()
        lagging_services = list({r["service"] for r in lagging_records if r["service"]})
        category_data = self.analyze_benchmark_by_category()
        low_cat = sorted(category_data.get("breakdown", []), key=lambda x: x["avg_benchmark_score"])
        top_lagging = (
            lagging_services[:5] if lagging_services else [b["category"] for b in low_cat[:3]]
        )
        recs: list[str] = []
        if avg_score < self._min_benchmark_score:
            recs.append(
                f"Avg benchmark score {avg_score:.1f} below minimum {self._min_benchmark_score}"
                " — prioritize security improvement initiatives"
            )
        if lagging_count > 0:
            recs.append(f"{lagging_count} assessments graded 'lagging' — address immediately")
        if not self._comparisons:
            recs.append("No benchmark comparisons registered — add peer comparisons for context")
        if not recs:
            recs.append("Security posture meets benchmark thresholds")
        return PostureBenchmarkReport(
            total_records=total,
            total_comparisons=len(self._comparisons),
            leading_count=leading_count,
            lagging_count=lagging_count,
            avg_benchmark_score=avg_score,
            by_category=by_category,
            by_grade=by_grade,
            by_source=by_source,
            top_lagging_services=top_lagging,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._comparisons.clear()
        logger.info("posture_benchmark.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        grade_dist: dict[str, int] = {}
        for r in self._records:
            grade_dist[r.grade.value] = grade_dist.get(r.grade.value, 0) + 1
        passing_count = sum(1 for r in self._records if r.passing)
        avg_score = (
            round(sum(r.benchmark_score for r in self._records) / len(self._records), 4)
            if self._records
            else 0.0
        )
        return {
            "total_records": len(self._records),
            "total_comparisons": len(self._comparisons),
            "passing_count": passing_count,
            "min_benchmark_score": self._min_benchmark_score,
            "avg_benchmark_score": avg_score,
            "grade_distribution": grade_dist,
            "unique_services": len({r.service for r in self._records if r.service}),
        }
