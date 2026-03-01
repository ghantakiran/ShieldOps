"""Toil Automation Tracker — track toil items, automation progress, and gaps."""

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
    MANUAL_DEPLOYMENT = "manual_deployment"
    CERTIFICATE_RENEWAL = "certificate_renewal"
    LOG_ANALYSIS = "log_analysis"
    INCIDENT_TRIAGE = "incident_triage"
    CONFIG_UPDATE = "config_update"


class AutomationStatus(StrEnum):
    FULLY_AUTOMATED = "fully_automated"
    PARTIALLY_AUTOMATED = "partially_automated"
    SCRIPTED = "scripted"
    MANUAL = "manual"
    NOT_STARTED = "not_started"


class AutomationROI(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    BREAK_EVEN = "break_even"
    NEGATIVE = "negative"


# --- Models ---


class ToilRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    toil_category: ToilCategory = ToilCategory.MANUAL_DEPLOYMENT
    automation_status: AutomationStatus = AutomationStatus.NOT_STARTED
    automation_roi: AutomationROI = AutomationROI.LOW
    time_savings: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AutomationProgress(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    toil_category: ToilCategory = ToilCategory.MANUAL_DEPLOYMENT
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ToilAutomationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_progress: int = 0
    manual_tasks: int = 0
    avg_time_savings: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_roi: dict[str, int] = Field(default_factory=dict)
    top_savings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ToilAutomationTracker:
    """Track toil items, identify manual tasks, and detect automation gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        min_automation_pct: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_automation_pct = min_automation_pct
        self._records: list[ToilRecord] = []
        self._progress: list[AutomationProgress] = []
        logger.info(
            "toil_automator.initialized",
            max_records=max_records,
            min_automation_pct=min_automation_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_toil(
        self,
        task_id: str,
        toil_category: ToilCategory = ToilCategory.MANUAL_DEPLOYMENT,
        automation_status: AutomationStatus = AutomationStatus.NOT_STARTED,
        automation_roi: AutomationROI = AutomationROI.LOW,
        time_savings: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ToilRecord:
        record = ToilRecord(
            task_id=task_id,
            toil_category=toil_category,
            automation_status=automation_status,
            automation_roi=automation_roi,
            time_savings=time_savings,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "toil_automator.toil_recorded",
            record_id=record.id,
            task_id=task_id,
            toil_category=toil_category.value,
            automation_status=automation_status.value,
        )
        return record

    def get_toil(self, record_id: str) -> ToilRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_toils(
        self,
        category: ToilCategory | None = None,
        status: AutomationStatus | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ToilRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.toil_category == category]
        if status is not None:
            results = [r for r in results if r.automation_status == status]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_progress(
        self,
        task_id: str,
        toil_category: ToilCategory = ToilCategory.MANUAL_DEPLOYMENT,
        value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AutomationProgress:
        progress = AutomationProgress(
            task_id=task_id,
            toil_category=toil_category,
            value=value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._progress.append(progress)
        if len(self._progress) > self._max_records:
            self._progress = self._progress[-self._max_records :]
        logger.info(
            "toil_automator.progress_added",
            task_id=task_id,
            toil_category=toil_category.value,
            value=value,
        )
        return progress

    # -- domain operations --------------------------------------------------

    def analyze_automation_coverage(self) -> dict[str, Any]:
        """Group by category; return count and avg time savings per category."""
        category_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.toil_category.value
            category_data.setdefault(key, []).append(r.time_savings)
        result: dict[str, Any] = {}
        for category, savings in category_data.items():
            result[category] = {
                "count": len(savings),
                "avg_time_savings": round(sum(savings) / len(savings), 2),
            }
        return result

    def identify_manual_tasks(self) -> list[dict[str, Any]]:
        """Return records where status == MANUAL or NOT_STARTED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.automation_status in (
                AutomationStatus.MANUAL,
                AutomationStatus.NOT_STARTED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "task_id": r.task_id,
                        "toil_category": r.toil_category.value,
                        "automation_status": r.automation_status.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_time_savings(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg time savings."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.time_savings)
        results: list[dict[str, Any]] = []
        for service, savings in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(savings),
                    "avg_time_savings": round(sum(savings) / len(savings), 2),
                }
            )
        results.sort(key=lambda x: x["avg_time_savings"], reverse=True)
        return results

    def detect_automation_gaps(self) -> dict[str, Any]:
        """Split-half on value; delta threshold 5.0."""
        if len(self._progress) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [p.value for p in self._progress]
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

    def generate_report(self) -> ToilAutomationReport:
        by_category: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_roi: dict[str, int] = {}
        for r in self._records:
            by_category[r.toil_category.value] = by_category.get(r.toil_category.value, 0) + 1
            by_status[r.automation_status.value] = by_status.get(r.automation_status.value, 0) + 1
            by_roi[r.automation_roi.value] = by_roi.get(r.automation_roi.value, 0) + 1
        manual_count = sum(
            1
            for r in self._records
            if r.automation_status in (AutomationStatus.MANUAL, AutomationStatus.NOT_STARTED)
        )
        savings = [r.time_savings for r in self._records]
        avg_savings = round(sum(savings) / len(savings), 2) if savings else 0.0
        rankings = self.rank_by_time_savings()
        top_savings = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        manual_rate = round(manual_count / len(self._records) * 100, 2) if self._records else 0.0
        automation_rate = 100.0 - manual_rate
        if automation_rate < self._min_automation_pct:
            recs.append(
                f"Automation rate {automation_rate}% below threshold ({self._min_automation_pct}%)"
            )
        if manual_count > 0:
            recs.append(f"{manual_count} manual task(s) detected — review automation")
        if not recs:
            recs.append("Toil automation coverage is acceptable")
        return ToilAutomationReport(
            total_records=len(self._records),
            total_progress=len(self._progress),
            manual_tasks=manual_count,
            avg_time_savings=avg_savings,
            by_category=by_category,
            by_status=by_status,
            by_roi=by_roi,
            top_savings=top_savings,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._progress.clear()
        logger.info("toil_automator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.toil_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_progress": len(self._progress),
            "min_automation_pct": self._min_automation_pct,
            "category_distribution": category_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_tasks": len({r.task_id for r in self._records}),
        }
