"""Compliance Automation Scorer — score and analyze compliance control automation levels."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AutomationLevel(StrEnum):
    FULLY_AUTOMATED = "fully_automated"
    MOSTLY_AUTOMATED = "mostly_automated"
    PARTIALLY_AUTOMATED = "partially_automated"
    MANUAL_WITH_TOOLS = "manual_with_tools"
    FULLY_MANUAL = "fully_manual"


class ControlCategory(StrEnum):
    ACCESS_CONTROL = "access_control"
    DATA_PROTECTION = "data_protection"
    MONITORING = "monitoring"
    INCIDENT_RESPONSE = "incident_response"
    CHANGE_MANAGEMENT = "change_management"


class AutomationPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


# --- Models ---


class AutomationScoreRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    control_name: str = ""
    automation_level: AutomationLevel = AutomationLevel.PARTIALLY_AUTOMATED
    category: ControlCategory = ControlCategory.MONITORING
    priority: AutomationPriority = AutomationPriority.MEDIUM
    automation_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationControl(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    control_name: str = ""
    category: ControlCategory = ControlCategory.MONITORING
    priority: AutomationPriority = AutomationPriority.MEDIUM
    target_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationScorerReport(BaseModel):
    total_records: int = 0
    total_controls: int = 0
    avg_automation_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    manual_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceAutomationScorer:
    """Score and analyze compliance control automation levels."""

    def __init__(
        self,
        max_records: int = 200000,
        min_automation_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_automation_pct = min_automation_pct
        self._records: list[AutomationScoreRecord] = []
        self._controls: list[AutomationControl] = []
        logger.info(
            "automation_scorer.initialized",
            max_records=max_records,
            min_automation_pct=min_automation_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_score(
        self,
        control_name: str,
        automation_level: AutomationLevel = AutomationLevel.PARTIALLY_AUTOMATED,
        category: ControlCategory = ControlCategory.MONITORING,
        priority: AutomationPriority = AutomationPriority.MEDIUM,
        automation_pct: float = 0.0,
        details: str = "",
    ) -> AutomationScoreRecord:
        record = AutomationScoreRecord(
            control_name=control_name,
            automation_level=automation_level,
            category=category,
            priority=priority,
            automation_pct=automation_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "automation_scorer.recorded",
            record_id=record.id,
            control_name=control_name,
            automation_pct=automation_pct,
        )
        return record

    def get_score(self, record_id: str) -> AutomationScoreRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_scores(
        self,
        category: ControlCategory | None = None,
        automation_level: AutomationLevel | None = None,
        limit: int = 50,
    ) -> list[AutomationScoreRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.category == category]
        if automation_level is not None:
            results = [r for r in results if r.automation_level == automation_level]
        return results[-limit:]

    def add_control(
        self,
        control_name: str,
        category: ControlCategory = ControlCategory.MONITORING,
        priority: AutomationPriority = AutomationPriority.MEDIUM,
        target_pct: float = 0.0,
        description: str = "",
    ) -> AutomationControl:
        control = AutomationControl(
            control_name=control_name,
            category=category,
            priority=priority,
            target_pct=target_pct,
            description=description,
        )
        self._controls.append(control)
        if len(self._controls) > self._max_records:
            self._controls = self._controls[-self._max_records :]
        logger.info(
            "automation_scorer.control_added",
            control_name=control_name,
            target_pct=target_pct,
        )
        return control

    # -- domain operations -----------------------------------------------

    def analyze_automation_by_category(self, category: ControlCategory) -> dict[str, Any]:
        """Analyze automation levels for a specific control category."""
        records = [r for r in self._records if r.category == category]
        if not records:
            return {"category": category.value, "status": "no_data"}
        avg_pct = round(sum(r.automation_pct for r in records) / len(records), 2)
        return {
            "category": category.value,
            "total": len(records),
            "avg_automation_pct": avg_pct,
            "meets_threshold": avg_pct >= self._min_automation_pct,
        }

    def identify_manual_controls(self) -> list[dict[str, Any]]:
        """Find controls with manual or manual-with-tools automation levels."""
        manual_levels = {AutomationLevel.FULLY_MANUAL, AutomationLevel.MANUAL_WITH_TOOLS}
        control_counts: dict[str, int] = {}
        for r in self._records:
            if r.automation_level in manual_levels:
                control_counts[r.control_name] = control_counts.get(r.control_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, count in control_counts.items():
            if count > 1:
                results.append({"control_name": name, "manual_count": count})
        results.sort(key=lambda x: x["manual_count"], reverse=True)
        return results

    def rank_by_automation_level(self) -> list[dict[str, Any]]:
        """Rank control categories by average automation percentage descending."""
        category_pcts: dict[str, list[float]] = {}
        for r in self._records:
            category_pcts.setdefault(r.category.value, []).append(r.automation_pct)
        results: list[dict[str, Any]] = []
        for cat, pcts in category_pcts.items():
            avg = round(sum(pcts) / len(pcts), 2)
            results.append({"category": cat, "avg_automation_pct": avg})
        results.sort(key=lambda x: x["avg_automation_pct"], reverse=True)
        return results

    def detect_automation_trends(self) -> list[dict[str, Any]]:
        """Detect automation trends for categories with sufficient data."""
        category_records: dict[str, list[AutomationScoreRecord]] = {}
        for r in self._records:
            category_records.setdefault(r.category.value, []).append(r)
        results: list[dict[str, Any]] = []
        for cat, records in category_records.items():
            if len(records) > 3:
                pcts = [r.automation_pct for r in records]
                trend = "improving" if pcts[-1] > pcts[0] else "declining"
                results.append(
                    {
                        "category": cat,
                        "record_count": len(records),
                        "trend": trend,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> AutomationScorerReport:
        by_category: dict[str, int] = {}
        by_level: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_level[r.automation_level.value] = by_level.get(r.automation_level.value, 0) + 1
        avg_pct = (
            round(
                sum(r.automation_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        manual_levels = {AutomationLevel.FULLY_MANUAL, AutomationLevel.MANUAL_WITH_TOOLS}
        manual_count = sum(1 for r in self._records if r.automation_level in manual_levels)
        recs: list[str] = []
        if manual_count > 0:
            recs.append(f"{manual_count} control(s) still fully or mostly manual")
        below_threshold = sum(
            1 for r in self._records if r.automation_pct < self._min_automation_pct
        )
        if below_threshold > 0:
            recs.append(f"{below_threshold} control(s) below minimum automation threshold")
        if not recs:
            recs.append("Compliance automation within acceptable limits")
        return AutomationScorerReport(
            total_records=len(self._records),
            total_controls=len(self._controls),
            avg_automation_pct=avg_pct,
            by_category=by_category,
            by_level=by_level,
            manual_count=manual_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._controls.clear()
        logger.info("automation_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_controls": len(self._controls),
            "min_automation_pct": self._min_automation_pct,
            "category_distribution": category_dist,
            "unique_controls": len({r.control_name for r in self._records}),
        }
