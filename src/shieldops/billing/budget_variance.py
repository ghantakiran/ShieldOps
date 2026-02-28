"""Budget Variance Tracker — track and analyze budget variance across cost categories."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class VarianceType(StrEnum):
    OVER_BUDGET = "over_budget"
    UNDER_BUDGET = "under_budget"
    ON_TARGET = "on_target"
    TRENDING_OVER = "trending_over"
    TRENDING_UNDER = "trending_under"


class VarianceSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class BudgetCategory(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    PERSONNEL = "personnel"
    LICENSING = "licensing"
    SERVICES = "services"
    OPERATIONS = "operations"


# --- Models ---


class VarianceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    budget_name: str = ""
    category: BudgetCategory = BudgetCategory.INFRASTRUCTURE
    variance_type: VarianceType = VarianceType.ON_TARGET
    severity: VarianceSeverity = VarianceSeverity.NEGLIGIBLE
    budgeted_amount: float = 0.0
    actual_amount: float = 0.0
    variance_pct: float = 0.0
    period: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class VarianceDetail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    budget_name: str = ""
    category: BudgetCategory = BudgetCategory.INFRASTRUCTURE
    line_item: str = ""
    variance_amount: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class BudgetVarianceReport(BaseModel):
    total_records: int = 0
    total_details: int = 0
    avg_variance_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_variance_type: dict[str, int] = Field(default_factory=dict)
    over_budget_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class BudgetVarianceTracker:
    """Track and analyze budget variance across cost categories."""

    def __init__(
        self,
        max_records: int = 200000,
        max_variance_pct: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._max_variance_pct = max_variance_pct
        self._records: list[VarianceRecord] = []
        self._details: list[VarianceDetail] = []
        logger.info(
            "budget_variance.initialized",
            max_records=max_records,
            max_variance_pct=max_variance_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _compute_variance_type(self, variance_pct: float) -> VarianceType:
        if variance_pct > 5:
            return VarianceType.OVER_BUDGET
        if variance_pct < -5:
            return VarianceType.UNDER_BUDGET
        return VarianceType.ON_TARGET

    def _compute_severity(self, variance_pct: float) -> VarianceSeverity:
        abs_pct = abs(variance_pct)
        if abs_pct >= 50:
            return VarianceSeverity.CRITICAL
        if abs_pct >= 25:
            return VarianceSeverity.HIGH
        if abs_pct >= self._max_variance_pct:
            return VarianceSeverity.MODERATE
        if abs_pct >= 5:
            return VarianceSeverity.LOW
        return VarianceSeverity.NEGLIGIBLE

    # -- record / get / list ---------------------------------------------

    def record_variance(
        self,
        budget_name: str,
        category: BudgetCategory = BudgetCategory.INFRASTRUCTURE,
        variance_type: VarianceType | None = None,
        severity: VarianceSeverity | None = None,
        budgeted_amount: float = 0.0,
        actual_amount: float = 0.0,
        variance_pct: float = 0.0,
        period: str = "",
        details: str = "",
    ) -> VarianceRecord:
        if variance_type is None:
            variance_type = self._compute_variance_type(variance_pct)
        if severity is None:
            severity = self._compute_severity(variance_pct)
        record = VarianceRecord(
            budget_name=budget_name,
            category=category,
            variance_type=variance_type,
            severity=severity,
            budgeted_amount=budgeted_amount,
            actual_amount=actual_amount,
            variance_pct=variance_pct,
            period=period,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "budget_variance.variance_recorded",
            record_id=record.id,
            budget_name=budget_name,
            category=category.value,
            variance_type=variance_type.value,
        )
        return record

    def get_variance(self, record_id: str) -> VarianceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_variances(
        self,
        budget_name: str | None = None,
        category: BudgetCategory | None = None,
        limit: int = 50,
    ) -> list[VarianceRecord]:
        results = list(self._records)
        if budget_name is not None:
            results = [r for r in results if r.budget_name == budget_name]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    def add_detail(
        self,
        budget_name: str,
        category: BudgetCategory = BudgetCategory.INFRASTRUCTURE,
        line_item: str = "",
        variance_amount: float = 0.0,
        reason: str = "",
    ) -> VarianceDetail:
        detail = VarianceDetail(
            budget_name=budget_name,
            category=category,
            line_item=line_item,
            variance_amount=variance_amount,
            reason=reason,
        )
        self._details.append(detail)
        if len(self._details) > self._max_records:
            self._details = self._details[-self._max_records :]
        logger.info(
            "budget_variance.detail_added",
            budget_name=budget_name,
            line_item=line_item,
            variance_amount=variance_amount,
        )
        return detail

    # -- domain operations -----------------------------------------------

    def analyze_variance_by_category(self, category: BudgetCategory) -> dict[str, Any]:
        """Analyze variance for a specific budget category."""
        records = [r for r in self._records if r.category == category]
        if not records:
            return {"category": category.value, "status": "no_data"}
        avg_variance = round(sum(r.variance_pct for r in records) / len(records), 2)
        total_budgeted = round(sum(r.budgeted_amount for r in records), 2)
        total_actual = round(sum(r.actual_amount for r in records), 2)
        over_budget = sum(1 for r in records if r.variance_type == VarianceType.OVER_BUDGET)
        return {
            "category": category.value,
            "total_records": len(records),
            "avg_variance_pct": avg_variance,
            "total_budgeted": total_budgeted,
            "total_actual": total_actual,
            "over_budget_count": over_budget,
            "exceeds_threshold": abs(avg_variance) >= self._max_variance_pct,
        }

    def identify_over_budget_items(self) -> list[dict[str, Any]]:
        """Find records with OVER_BUDGET or TRENDING_OVER status."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.variance_type in (VarianceType.OVER_BUDGET, VarianceType.TRENDING_OVER):
                results.append(
                    {
                        "record_id": r.id,
                        "budget_name": r.budget_name,
                        "category": r.category.value,
                        "variance_type": r.variance_type.value,
                        "severity": r.severity.value,
                        "variance_pct": r.variance_pct,
                        "actual_amount": r.actual_amount,
                    }
                )
        results.sort(key=lambda x: x["variance_pct"], reverse=True)
        return results

    def rank_by_variance_pct(self) -> list[dict[str, Any]]:
        """Rank all records by absolute variance percentage descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "record_id": r.id,
                    "budget_name": r.budget_name,
                    "category": r.category.value,
                    "variance_pct": r.variance_pct,
                    "abs_variance_pct": abs(r.variance_pct),
                    "variance_type": r.variance_type.value,
                    "severity": r.severity.value,
                }
            )
        results.sort(key=lambda x: x["abs_variance_pct"], reverse=True)
        return results

    def detect_variance_trends(self) -> list[dict[str, Any]]:
        """Detect budgets with worsening variance over time."""
        budget_variances: dict[str, list[float]] = {}
        for r in self._records:
            budget_variances.setdefault(r.budget_name, []).append(r.variance_pct)
        trends: list[dict[str, Any]] = []
        for budget, variances in budget_variances.items():
            if len(variances) >= 2:
                delta = variances[-1] - variances[0]
                trends.append(
                    {
                        "budget_name": budget,
                        "variance_delta": round(delta, 2),
                        "worsening": delta > 0,
                        "record_count": len(variances),
                        "latest_variance_pct": variances[-1],
                    }
                )
        trends.sort(key=lambda x: x["variance_delta"], reverse=True)
        return trends

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> BudgetVarianceReport:
        by_category: dict[str, int] = {}
        by_variance_type: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_variance_type[r.variance_type.value] = (
                by_variance_type.get(r.variance_type.value, 0) + 1
            )
        avg_variance = (
            round(sum(r.variance_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        over_budget_count = sum(
            1
            for r in self._records
            if r.variance_type in (VarianceType.OVER_BUDGET, VarianceType.TRENDING_OVER)
        )
        recs: list[str] = []
        if abs(avg_variance) >= self._max_variance_pct:
            recs.append(
                f"Average variance {avg_variance}% exceeds threshold {self._max_variance_pct}%"
            )
        if over_budget_count > 0:
            recs.append(f"{over_budget_count} budget(s) are over target or trending over")
        worsening = [t for t in self.detect_variance_trends() if t["worsening"]]
        if worsening:
            recs.append(f"{len(worsening)} budget(s) showing worsening variance")
        if not recs:
            recs.append("Budget variance is within acceptable limits")
        return BudgetVarianceReport(
            total_records=len(self._records),
            total_details=len(self._details),
            avg_variance_pct=avg_variance,
            by_category=by_category,
            by_variance_type=by_variance_type,
            over_budget_count=over_budget_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._details.clear()
        logger.info("budget_variance.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        severity_dist: dict[str, int] = {}
        for r in self._records:
            key = r.severity.value
            severity_dist[key] = severity_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_details": len(self._details),
            "max_variance_pct": self._max_variance_pct,
            "severity_distribution": severity_dist,
            "unique_budgets": len({r.budget_name for r in self._records}),
        }
