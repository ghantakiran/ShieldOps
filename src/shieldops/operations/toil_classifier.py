"""Operational Toil Classifier — classify and track operational toil."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ToilCategory(StrEnum):
    MANUAL_INTERVENTION = "manual_intervention"
    REPETITIVE_TASK = "repetitive_task"
    INTERRUPT_DRIVEN = "interrupt_driven"
    SCALING_LIMITATION = "scaling_limitation"
    PROCESS_OVERHEAD = "process_overhead"


class ToilImpact(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


class AutomationPotential(StrEnum):
    FULLY_AUTOMATABLE = "fully_automatable"
    MOSTLY_AUTOMATABLE = "mostly_automatable"
    PARTIALLY_AUTOMATABLE = "partially_automatable"
    DIFFICULT_TO_AUTOMATE = "difficult_to_automate"
    NOT_AUTOMATABLE = "not_automatable"


# --- Models ---


class ToilRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_name: str = ""
    category: ToilCategory = ToilCategory.MANUAL_INTERVENTION
    impact: ToilImpact = ToilImpact.MODERATE
    automation_potential: AutomationPotential = AutomationPotential.PARTIALLY_AUTOMATABLE
    hours_per_week: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ToilClassification(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_name: str = ""
    category: ToilCategory = ToilCategory.MANUAL_INTERVENTION
    impact: ToilImpact = ToilImpact.MODERATE
    automation_potential: AutomationPotential = AutomationPotential.PARTIALLY_AUTOMATABLE
    estimated_savings_hours: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ToilClassifierReport(BaseModel):
    total_toil_records: int = 0
    total_classifications: int = 0
    total_hours_per_week: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    high_impact_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class OperationalToilClassifier:
    """Classify and track operational toil."""

    def __init__(
        self,
        max_records: int = 200000,
        max_toil_hours_weekly: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._max_toil_hours_weekly = max_toil_hours_weekly
        self._records: list[ToilRecord] = []
        self._classifications: list[ToilClassification] = []
        logger.info(
            "toil_classifier.initialized",
            max_records=max_records,
            max_toil_hours_weekly=max_toil_hours_weekly,
        )

    # -- record / get / list -------------------------------------------

    def record_toil(
        self,
        task_name: str,
        category: ToilCategory = ToilCategory.MANUAL_INTERVENTION,
        impact: ToilImpact = ToilImpact.MODERATE,
        automation_potential: AutomationPotential = AutomationPotential.PARTIALLY_AUTOMATABLE,
        hours_per_week: float = 0.0,
        details: str = "",
    ) -> ToilRecord:
        record = ToilRecord(
            task_name=task_name,
            category=category,
            impact=impact,
            automation_potential=automation_potential,
            hours_per_week=hours_per_week,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "toil_classifier.toil_recorded",
            record_id=record.id,
            task_name=task_name,
            category=category.value,
            impact=impact.value,
        )
        return record

    def get_toil(self, record_id: str) -> ToilRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_toils(
        self,
        task_name: str | None = None,
        category: ToilCategory | None = None,
        limit: int = 50,
    ) -> list[ToilRecord]:
        results = list(self._records)
        if task_name is not None:
            results = [r for r in results if r.task_name == task_name]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    def add_classification(
        self,
        task_name: str,
        category: ToilCategory = ToilCategory.MANUAL_INTERVENTION,
        impact: ToilImpact = ToilImpact.MODERATE,
        automation_potential: AutomationPotential = AutomationPotential.PARTIALLY_AUTOMATABLE,
        estimated_savings_hours: float = 0.0,
        details: str = "",
    ) -> ToilClassification:
        classification = ToilClassification(
            task_name=task_name,
            category=category,
            impact=impact,
            automation_potential=automation_potential,
            estimated_savings_hours=estimated_savings_hours,
            details=details,
        )
        self._classifications.append(classification)
        if len(self._classifications) > self._max_records:
            self._classifications = self._classifications[-self._max_records :]
        logger.info(
            "toil_classifier.classification_added",
            task_name=task_name,
            category=category.value,
            impact=impact.value,
        )
        return classification

    # -- domain operations --------------------------------------------

    def analyze_toil_by_category(self, task_name: str) -> dict[str, Any]:
        """Analyze toil for a specific task."""
        records = [r for r in self._records if r.task_name == task_name]
        if not records:
            return {"task_name": task_name, "status": "no_data"}
        total_hours = round(sum(r.hours_per_week for r in records), 2)
        high_impact_count = sum(
            1 for r in records if r.impact in (ToilImpact.CRITICAL, ToilImpact.HIGH)
        )
        return {
            "task_name": task_name,
            "record_count": len(records),
            "total_hours_per_week": total_hours,
            "high_impact_count": high_impact_count,
            "exceeds_threshold": total_hours > self._max_toil_hours_weekly,
        }

    def identify_high_impact_toil(self) -> list[dict[str, Any]]:
        """Find tasks with repeated high/critical impact toil."""
        impact_counts: dict[str, int] = {}
        for r in self._records:
            if r.impact in (ToilImpact.CRITICAL, ToilImpact.HIGH):
                impact_counts[r.task_name] = impact_counts.get(r.task_name, 0) + 1
        results: list[dict[str, Any]] = []
        for task, count in impact_counts.items():
            if count > 1:
                results.append(
                    {
                        "task_name": task,
                        "high_impact_count": count,
                    }
                )
        results.sort(key=lambda x: x["high_impact_count"], reverse=True)
        return results

    def rank_by_automation_potential(self) -> list[dict[str, Any]]:
        """Rank tasks by hours per week descending (most toil first)."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self._records:
            totals[r.task_name] = totals.get(r.task_name, 0.0) + r.hours_per_week
            counts[r.task_name] = counts.get(r.task_name, 0) + 1
        results: list[dict[str, Any]] = []
        for task in totals:
            avg = round(totals[task] / counts[task], 2)
            results.append(
                {
                    "task_name": task,
                    "avg_hours_per_week": avg,
                }
            )
        results.sort(key=lambda x: x["avg_hours_per_week"], reverse=True)
        return results

    def detect_toil_trends(self) -> list[dict[str, Any]]:
        """Detect tasks with >3 records exceeding weekly toil threshold."""
        over_threshold: dict[str, int] = {}
        for r in self._records:
            if r.hours_per_week > self._max_toil_hours_weekly:
                over_threshold[r.task_name] = over_threshold.get(r.task_name, 0) + 1
        results: list[dict[str, Any]] = []
        for task, count in over_threshold.items():
            if count > 3:
                results.append(
                    {
                        "task_name": task,
                        "over_threshold_count": count,
                        "trend_detected": True,
                    }
                )
        results.sort(key=lambda x: x["over_threshold_count"], reverse=True)
        return results

    # -- report / stats -----------------------------------------------

    def generate_report(self) -> ToilClassifierReport:
        by_category: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_impact[r.impact.value] = by_impact.get(r.impact.value, 0) + 1
        total_hours = round(sum(r.hours_per_week for r in self._records), 2)
        high_impact = sum(1 for _ in self.identify_high_impact_toil())
        recs: list[str] = []
        if total_hours > self._max_toil_hours_weekly:
            recs.append(
                f"Total toil {total_hours}h/week exceeds {self._max_toil_hours_weekly}h threshold"
            )
        if high_impact > 0:
            recs.append(f"{high_impact} task(s) with repeated high-impact toil")
        trends = len(self.detect_toil_trends())
        if trends > 0:
            recs.append(f"{trends} task(s) detected with toil trends")
        if not recs:
            recs.append("Operational toil within acceptable limits")
        return ToilClassifierReport(
            total_toil_records=len(self._records),
            total_classifications=len(self._classifications),
            total_hours_per_week=total_hours,
            by_category=by_category,
            by_impact=by_impact,
            high_impact_count=high_impact,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._classifications.clear()
        logger.info("toil_classifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_toil_records": len(self._records),
            "total_classifications": len(self._classifications),
            "max_toil_hours_weekly": self._max_toil_hours_weekly,
            "category_distribution": category_dist,
            "unique_tasks": len({r.task_name for r in self._records}),
        }
