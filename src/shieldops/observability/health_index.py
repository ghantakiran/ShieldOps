"""Platform Health Index — track composite health scores across service dimensions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HealthDimension(StrEnum):
    AVAILABILITY = "availability"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class IndexGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class TrendDirection(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class HealthIndexRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    dimension: HealthDimension = HealthDimension.AVAILABILITY
    grade: IndexGrade = IndexGrade.GOOD
    trend: TrendDirection = TrendDirection.STABLE
    score_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DimensionScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dimension_name: str = ""
    dimension: HealthDimension = HealthDimension.AVAILABILITY
    grade: IndexGrade = IndexGrade.GOOD
    weight: float = 1.0
    target_score_pct: float = 90.0
    created_at: float = Field(default_factory=time.time)


class PlatformHealthReport(BaseModel):
    total_indices: int = 0
    total_dimensions: int = 0
    healthy_rate_pct: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PlatformHealthIndex:
    """Track composite health scores across service dimensions."""

    def __init__(
        self,
        max_records: int = 200000,
        min_score_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_score_pct = min_score_pct
        self._records: list[HealthIndexRecord] = []
        self._dimensions: list[DimensionScore] = []
        logger.info(
            "health_index.initialized",
            max_records=max_records,
            min_score_pct=min_score_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_index(
        self,
        service_name: str,
        dimension: HealthDimension = HealthDimension.AVAILABILITY,
        grade: IndexGrade = IndexGrade.GOOD,
        trend: TrendDirection = TrendDirection.STABLE,
        score_pct: float = 0.0,
        details: str = "",
    ) -> HealthIndexRecord:
        record = HealthIndexRecord(
            service_name=service_name,
            dimension=dimension,
            grade=grade,
            trend=trend,
            score_pct=score_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "health_index.index_recorded",
            record_id=record.id,
            service_name=service_name,
            dimension=dimension.value,
            grade=grade.value,
        )
        return record

    def get_index(self, record_id: str) -> HealthIndexRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_indices(
        self,
        service_name: str | None = None,
        dimension: HealthDimension | None = None,
        limit: int = 50,
    ) -> list[HealthIndexRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if dimension is not None:
            results = [r for r in results if r.dimension == dimension]
        return results[-limit:]

    def add_dimension_score(
        self,
        dimension_name: str,
        dimension: HealthDimension = HealthDimension.AVAILABILITY,
        grade: IndexGrade = IndexGrade.GOOD,
        weight: float = 1.0,
        target_score_pct: float = 90.0,
    ) -> DimensionScore:
        dim = DimensionScore(
            dimension_name=dimension_name,
            dimension=dimension,
            grade=grade,
            weight=weight,
            target_score_pct=target_score_pct,
        )
        self._dimensions.append(dim)
        if len(self._dimensions) > self._max_records:
            self._dimensions = self._dimensions[-self._max_records :]
        logger.info(
            "health_index.dimension_added",
            dimension_name=dimension_name,
            dimension=dimension.value,
            grade=grade.value,
        )
        return dim

    # -- domain operations -----------------------------------------------

    def analyze_platform_health(self, service_name: str) -> dict[str, Any]:
        """Analyze health for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_score = round(sum(r.score_pct for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "avg_score": avg_score,
            "record_count": len(records),
            "meets_threshold": avg_score >= self._min_score_pct,
        }

    def identify_weak_dimensions(self) -> list[dict[str, Any]]:
        """Find services with >1 POOR/CRITICAL grade."""
        weak_counts: dict[str, int] = {}
        for r in self._records:
            if r.grade in (IndexGrade.POOR, IndexGrade.CRITICAL):
                weak_counts[r.service_name] = weak_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in weak_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "weak_count": count,
                    }
                )
        results.sort(key=lambda x: x["weak_count"], reverse=True)
        return results

    def rank_by_health_score(self) -> list[dict[str, Any]]:
        """Rank services by average score_pct descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service_name, []).append(r.score_pct)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_score_pct": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score_pct"], reverse=True)
        return results

    def detect_health_trends(self) -> list[dict[str, Any]]:
        """Detect services with >3 records for trend analysis."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "record_count": count,
                        "trend_available": True,
                    }
                )
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> PlatformHealthReport:
        by_dimension: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.dimension.value] = by_dimension.get(r.dimension.value, 0) + 1
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
        healthy_count = sum(
            1 for r in self._records if r.grade in (IndexGrade.EXCELLENT, IndexGrade.GOOD)
        )
        healthy_rate = round(healthy_count / len(self._records) * 100, 2) if self._records else 0.0
        critical_count = sum(1 for r in self._records if r.grade == IndexGrade.CRITICAL)
        weak = len(self.identify_weak_dimensions())
        recs: list[str] = []
        if self._records and healthy_rate < self._min_score_pct:
            recs.append(f"Healthy rate {healthy_rate}% is below {self._min_score_pct}% threshold")
        if weak > 0:
            recs.append(f"{weak} service(s) with weak dimensions")
        if critical_count > 0:
            recs.append(f"{critical_count} critical index record(s) detected")
        if not recs:
            recs.append("Platform health meets targets")
        return PlatformHealthReport(
            total_indices=len(self._records),
            total_dimensions=len(self._dimensions),
            healthy_rate_pct=healthy_rate,
            by_dimension=by_dimension,
            by_grade=by_grade,
            critical_count=critical_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._dimensions.clear()
        logger.info("health_index.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dimension_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dimension.value
            dimension_dist[key] = dimension_dist.get(key, 0) + 1
        return {
            "total_indices": len(self._records),
            "total_dimensions": len(self._dimensions),
            "min_score_pct": self._min_score_pct,
            "dimension_distribution": dimension_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
