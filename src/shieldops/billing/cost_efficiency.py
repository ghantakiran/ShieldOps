"""Cost Efficiency Scorer — score and track cost efficiency across cloud resources."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EfficiencyCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    SERVICES = "services"


class EfficiencyGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    WASTEFUL = "wasteful"


class OptimizationPotential(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"
    NONE = "none"


# --- Models ---


class EfficiencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    category: EfficiencyCategory = EfficiencyCategory.COMPUTE
    grade: EfficiencyGrade = EfficiencyGrade.ADEQUATE
    potential: OptimizationPotential = OptimizationPotential.MODERATE
    efficiency_pct: float = 0.0
    monthly_cost: float = 0.0
    wasted_spend: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class EfficiencyMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    category: EfficiencyCategory = EfficiencyCategory.COMPUTE
    metric_name: str = ""
    value: float = 0.0
    unit: str = ""
    created_at: float = Field(default_factory=time.time)


class CostEfficiencyReport(BaseModel):
    total_records: int = 0
    total_metrics: int = 0
    avg_efficiency_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    wasteful_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostEfficiencyScorer:
    """Score and track cost efficiency across cloud resources."""

    def __init__(
        self,
        max_records: int = 200000,
        min_efficiency_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_efficiency_pct = min_efficiency_pct
        self._records: list[EfficiencyRecord] = []
        self._metrics: list[EfficiencyMetric] = []
        logger.info(
            "cost_efficiency.initialized",
            max_records=max_records,
            min_efficiency_pct=min_efficiency_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _pct_to_grade(self, efficiency_pct: float) -> EfficiencyGrade:
        if efficiency_pct >= 90:
            return EfficiencyGrade.EXCELLENT
        if efficiency_pct >= 75:
            return EfficiencyGrade.GOOD
        if efficiency_pct >= 60:
            return EfficiencyGrade.ADEQUATE
        if efficiency_pct >= 40:
            return EfficiencyGrade.POOR
        return EfficiencyGrade.WASTEFUL

    # -- record / get / list ---------------------------------------------

    def record_efficiency(
        self,
        service_name: str,
        category: EfficiencyCategory = EfficiencyCategory.COMPUTE,
        grade: EfficiencyGrade | None = None,
        potential: OptimizationPotential = OptimizationPotential.MODERATE,
        efficiency_pct: float = 0.0,
        monthly_cost: float = 0.0,
        wasted_spend: float = 0.0,
        details: str = "",
    ) -> EfficiencyRecord:
        if grade is None:
            grade = self._pct_to_grade(efficiency_pct)
        record = EfficiencyRecord(
            service_name=service_name,
            category=category,
            grade=grade,
            potential=potential,
            efficiency_pct=efficiency_pct,
            monthly_cost=monthly_cost,
            wasted_spend=wasted_spend,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_efficiency.efficiency_recorded",
            record_id=record.id,
            service_name=service_name,
            category=category.value,
            grade=grade.value,
        )
        return record

    def get_efficiency(self, record_id: str) -> EfficiencyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_efficiencies(
        self,
        service_name: str | None = None,
        category: EfficiencyCategory | None = None,
        limit: int = 50,
    ) -> list[EfficiencyRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    def add_metric(
        self,
        service_name: str,
        category: EfficiencyCategory = EfficiencyCategory.COMPUTE,
        metric_name: str = "",
        value: float = 0.0,
        unit: str = "",
    ) -> EfficiencyMetric:
        metric = EfficiencyMetric(
            service_name=service_name,
            category=category,
            metric_name=metric_name,
            value=value,
            unit=unit,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "cost_efficiency.metric_added",
            service_name=service_name,
            metric_name=metric_name,
            value=value,
        )
        return metric

    # -- domain operations -----------------------------------------------

    def analyze_efficiency_by_service(self, service_name: str) -> dict[str, Any]:
        """Analyze cost efficiency for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_efficiency = round(sum(r.efficiency_pct for r in records) / len(records), 2)
        total_cost = round(sum(r.monthly_cost for r in records), 2)
        total_wasted = round(sum(r.wasted_spend for r in records), 2)
        return {
            "service_name": service_name,
            "total_resources": len(records),
            "avg_efficiency_pct": avg_efficiency,
            "total_monthly_cost": total_cost,
            "total_wasted_spend": total_wasted,
            "meets_threshold": avg_efficiency >= self._min_efficiency_pct,
        }

    def identify_wasteful_resources(self) -> list[dict[str, Any]]:
        """Find resources graded POOR or WASTEFUL."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.grade in (EfficiencyGrade.POOR, EfficiencyGrade.WASTEFUL):
                results.append(
                    {
                        "record_id": r.id,
                        "service_name": r.service_name,
                        "category": r.category.value,
                        "grade": r.grade.value,
                        "efficiency_pct": r.efficiency_pct,
                        "wasted_spend": r.wasted_spend,
                    }
                )
        results.sort(key=lambda x: x["wasted_spend"], reverse=True)
        return results

    def rank_by_efficiency_score(self) -> list[dict[str, Any]]:
        """Rank all records by efficiency percentage ascending (worst first)."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "record_id": r.id,
                    "service_name": r.service_name,
                    "efficiency_pct": r.efficiency_pct,
                    "grade": r.grade.value,
                    "potential": r.potential.value,
                }
            )
        results.sort(key=lambda x: x["efficiency_pct"])
        return results

    def detect_efficiency_trends(self) -> list[dict[str, Any]]:
        """Detect services with declining efficiency over time."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service_name, []).append(r.efficiency_pct)
        trends: list[dict[str, Any]] = []
        for service, scores in service_scores.items():
            if len(scores) >= 2:
                delta = scores[-1] - scores[0]
                trends.append(
                    {
                        "service_name": service,
                        "efficiency_delta": round(delta, 2),
                        "declining": delta < 0,
                        "record_count": len(scores),
                        "latest_efficiency_pct": scores[-1],
                    }
                )
        trends.sort(key=lambda x: x["efficiency_delta"])
        return trends

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> CostEfficiencyReport:
        by_category: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
        avg_efficiency = (
            round(sum(r.efficiency_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        wasteful_count = sum(
            1 for r in self._records if r.grade in (EfficiencyGrade.POOR, EfficiencyGrade.WASTEFUL)
        )
        recs: list[str] = []
        if self._records and avg_efficiency < self._min_efficiency_pct:
            recs.append(
                f"Average efficiency {avg_efficiency}% is below "
                f"{self._min_efficiency_pct}% threshold"
            )
        if wasteful_count > 0:
            recs.append(f"{wasteful_count} resource(s) graded poor or wasteful")
        declining = [t for t in self.detect_efficiency_trends() if t["declining"]]
        if declining:
            recs.append(f"{len(declining)} service(s) showing declining efficiency")
        if not recs:
            recs.append("Cost efficiency meets optimization targets")
        return CostEfficiencyReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            avg_efficiency_pct=avg_efficiency,
            by_category=by_category,
            by_grade=by_grade,
            wasteful_count=wasteful_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("cost_efficiency.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        grade_dist: dict[str, int] = {}
        for r in self._records:
            key = r.grade.value
            grade_dist[key] = grade_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_efficiency_pct": self._min_efficiency_pct,
            "grade_distribution": grade_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
