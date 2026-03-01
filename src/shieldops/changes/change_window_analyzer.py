"""Change Window Analyzer — analyze change window utilization, detect out-of-window changes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WindowCompliance(StrEnum):
    WITHIN_WINDOW = "within_window"
    EARLY = "early"
    LATE = "late"
    EMERGENCY = "emergency"
    UNAUTHORIZED = "unauthorized"


class WindowType(StrEnum):
    STANDARD = "standard"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"
    FREEZE = "freeze"
    CUSTOM = "custom"


class SchedulingEfficiency(StrEnum):
    OPTIMAL = "optimal"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    WASTED = "wasted"


# --- Models ---


class WindowRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    window_id: str = ""
    window_compliance: WindowCompliance = WindowCompliance.WITHIN_WINDOW
    window_type: WindowType = WindowType.STANDARD
    scheduling_efficiency: SchedulingEfficiency = SchedulingEfficiency.GOOD
    utilization_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WindowMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    window_id: str = ""
    window_compliance: WindowCompliance = WindowCompliance.WITHIN_WINDOW
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeWindowReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    non_compliant_count: int = 0
    avg_utilization_pct: float = 0.0
    by_compliance: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_efficiency: dict[str, int] = Field(default_factory=dict)
    top_non_compliant: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeWindowAnalyzer:
    """Analyze change window utilization, detect out-of-window changes, optimize scheduling."""

    def __init__(
        self,
        max_records: int = 200000,
        min_compliance_pct: float = 85.0,
    ) -> None:
        self._max_records = max_records
        self._min_compliance_pct = min_compliance_pct
        self._records: list[WindowRecord] = []
        self._metrics: list[WindowMetric] = []
        logger.info(
            "change_window_analyzer.initialized",
            max_records=max_records,
            min_compliance_pct=min_compliance_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_window(
        self,
        window_id: str,
        window_compliance: WindowCompliance = WindowCompliance.WITHIN_WINDOW,
        window_type: WindowType = WindowType.STANDARD,
        scheduling_efficiency: SchedulingEfficiency = SchedulingEfficiency.GOOD,
        utilization_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> WindowRecord:
        record = WindowRecord(
            window_id=window_id,
            window_compliance=window_compliance,
            window_type=window_type,
            scheduling_efficiency=scheduling_efficiency,
            utilization_pct=utilization_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "change_window_analyzer.window_recorded",
            record_id=record.id,
            window_id=window_id,
            window_compliance=window_compliance.value,
            window_type=window_type.value,
        )
        return record

    def get_window(self, record_id: str) -> WindowRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_windows(
        self,
        compliance: WindowCompliance | None = None,
        window_type: WindowType | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WindowRecord]:
        results = list(self._records)
        if compliance is not None:
            results = [r for r in results if r.window_compliance == compliance]
        if window_type is not None:
            results = [r for r in results if r.window_type == window_type]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        window_id: str,
        window_compliance: WindowCompliance = WindowCompliance.WITHIN_WINDOW,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> WindowMetric:
        metric = WindowMetric(
            window_id=window_id,
            window_compliance=window_compliance,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "change_window_analyzer.metric_added",
            window_id=window_id,
            window_compliance=window_compliance.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_window_distribution(self) -> dict[str, Any]:
        """Group by window_compliance; return count and avg utilization_pct."""
        compliance_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.window_compliance.value
            compliance_data.setdefault(key, []).append(r.utilization_pct)
        result: dict[str, Any] = {}
        for compliance, pcts in compliance_data.items():
            result[compliance] = {
                "count": len(pcts),
                "avg_utilization_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_non_compliant(self) -> list[dict[str, Any]]:
        """Return records where window_compliance is LATE, EMERGENCY, or UNAUTHORIZED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.window_compliance in (
                WindowCompliance.LATE,
                WindowCompliance.EMERGENCY,
                WindowCompliance.UNAUTHORIZED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "window_id": r.window_id,
                        "window_compliance": r.window_compliance.value,
                        "utilization_pct": r.utilization_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_utilization(self) -> list[dict[str, Any]]:
        """Group by service, avg utilization_pct, sort ascending (worst first)."""
        svc_pcts: dict[str, list[float]] = {}
        for r in self._records:
            svc_pcts.setdefault(r.service, []).append(r.utilization_pct)
        results: list[dict[str, Any]] = []
        for svc, pcts in svc_pcts.items():
            results.append(
                {
                    "service": svc,
                    "avg_utilization_pct": round(sum(pcts) / len(pcts), 2),
                }
            )
        results.sort(key=lambda x: x["avg_utilization_pct"])
        return results

    def detect_window_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [m.metric_score for m in self._metrics]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ChangeWindowReport:
        by_compliance: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_efficiency: dict[str, int] = {}
        for r in self._records:
            by_compliance[r.window_compliance.value] = (
                by_compliance.get(r.window_compliance.value, 0) + 1
            )
            by_type[r.window_type.value] = by_type.get(r.window_type.value, 0) + 1
            by_efficiency[r.scheduling_efficiency.value] = (
                by_efficiency.get(r.scheduling_efficiency.value, 0) + 1
            )
        non_compliant_count = sum(
            1
            for r in self._records
            if r.window_compliance
            in (
                WindowCompliance.LATE,
                WindowCompliance.EMERGENCY,
                WindowCompliance.UNAUTHORIZED,
            )
        )
        pcts = [r.utilization_pct for r in self._records]
        avg_utilization_pct = round(sum(pcts) / len(pcts), 2) if pcts else 0.0
        nc_list = self.identify_non_compliant()
        top_non_compliant = [o["window_id"] for o in nc_list[:5]]
        recs: list[str] = []
        if non_compliant_count > 0:
            recs.append(f"{non_compliant_count} non-compliant change(s) — review scheduling")
        if self._records and avg_utilization_pct < self._min_compliance_pct:
            recs.append(
                f"Avg utilization {avg_utilization_pct}% below threshold "
                f"({self._min_compliance_pct}%)"
            )
        if not recs:
            recs.append("Change window compliance levels are healthy")
        return ChangeWindowReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            non_compliant_count=non_compliant_count,
            avg_utilization_pct=avg_utilization_pct,
            by_compliance=by_compliance,
            by_type=by_type,
            by_efficiency=by_efficiency,
            top_non_compliant=top_non_compliant,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("change_window_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        compliance_dist: dict[str, int] = {}
        for r in self._records:
            key = r.window_compliance.value
            compliance_dist[key] = compliance_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_compliance_pct": self._min_compliance_pct,
            "compliance_distribution": compliance_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
