"""SLO Window Analyzer — analyze SLO compliance across different time windows."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WindowDuration(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class ComplianceStatus(StrEnum):
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    BREACHING = "breaching"
    BREACHED = "breached"
    UNKNOWN = "unknown"


class WindowStrategy(StrEnum):
    ROLLING = "rolling"
    CALENDAR = "calendar"
    SLIDING = "sliding"
    FIXED = "fixed"
    ADAPTIVE = "adaptive"


# --- Models ---


class WindowRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_id: str = ""
    window_duration: WindowDuration = WindowDuration.MONTHLY
    compliance_status: ComplianceStatus = ComplianceStatus.UNKNOWN
    window_strategy: WindowStrategy = WindowStrategy.ROLLING
    compliance_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WindowEvaluation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_id: str = ""
    window_duration: WindowDuration = WindowDuration.MONTHLY
    eval_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SLOWindowReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_evaluations: int = 0
    breaching_count: int = 0
    avg_compliance_pct: float = 0.0
    by_duration: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    top_breaching: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOWindowAnalyzer:
    """Analyze SLO compliance across different time windows."""

    def __init__(
        self,
        max_records: int = 200000,
        min_compliance_pct: float = 95.0,
    ) -> None:
        self._max_records = max_records
        self._min_compliance_pct = min_compliance_pct
        self._records: list[WindowRecord] = []
        self._metrics: list[WindowEvaluation] = []
        logger.info(
            "slo_window.initialized",
            max_records=max_records,
            min_compliance_pct=min_compliance_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_window(
        self,
        slo_id: str,
        window_duration: WindowDuration = WindowDuration.MONTHLY,
        compliance_status: ComplianceStatus = ComplianceStatus.UNKNOWN,
        window_strategy: WindowStrategy = WindowStrategy.ROLLING,
        compliance_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> WindowRecord:
        record = WindowRecord(
            slo_id=slo_id,
            window_duration=window_duration,
            compliance_status=compliance_status,
            window_strategy=window_strategy,
            compliance_pct=compliance_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_window.window_recorded",
            record_id=record.id,
            slo_id=slo_id,
            window_duration=window_duration.value,
            compliance_status=compliance_status.value,
        )
        return record

    def get_window(self, record_id: str) -> WindowRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_windows(
        self,
        duration: WindowDuration | None = None,
        status: ComplianceStatus | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WindowRecord]:
        results = list(self._records)
        if duration is not None:
            results = [r for r in results if r.window_duration == duration]
        if status is not None:
            results = [r for r in results if r.compliance_status == status]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_evaluation(
        self,
        slo_id: str,
        window_duration: WindowDuration = WindowDuration.MONTHLY,
        eval_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> WindowEvaluation:
        metric = WindowEvaluation(
            slo_id=slo_id,
            window_duration=window_duration,
            eval_score=eval_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "slo_window.evaluation_added",
            slo_id=slo_id,
            window_duration=window_duration.value,
            eval_score=eval_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_window_compliance(self) -> dict[str, Any]:
        """Group by window_duration; return count and avg compliance_pct."""
        dur_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.window_duration.value
            dur_data.setdefault(key, []).append(r.compliance_pct)
        result: dict[str, Any] = {}
        for dur, pcts in dur_data.items():
            result[dur] = {
                "count": len(pcts),
                "avg_compliance_pct": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_breaching_windows(self) -> list[dict[str, Any]]:
        """Return records where compliance_status == BREACHING or BREACHED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_status in (ComplianceStatus.BREACHING, ComplianceStatus.BREACHED):
                results.append(
                    {
                        "record_id": r.id,
                        "slo_id": r.slo_id,
                        "window_duration": r.window_duration.value,
                        "compliance_pct": r.compliance_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_compliance(self) -> list[dict[str, Any]]:
        """Group by service, avg compliance_pct, sort ascending."""
        svc_pcts: dict[str, list[float]] = {}
        for r in self._records:
            svc_pcts.setdefault(r.service, []).append(r.compliance_pct)
        results: list[dict[str, Any]] = []
        for svc, pcts in svc_pcts.items():
            results.append(
                {
                    "service": svc,
                    "avg_compliance_pct": round(sum(pcts) / len(pcts), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_pct"])
        return results

    def detect_compliance_trends(self) -> dict[str, Any]:
        """Split-half comparison on eval_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [m.eval_score for m in self._metrics]
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

    def generate_report(self) -> SLOWindowReport:
        by_duration: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_duration[r.window_duration.value] = by_duration.get(r.window_duration.value, 0) + 1
            by_status[r.compliance_status.value] = by_status.get(r.compliance_status.value, 0) + 1
            by_strategy[r.window_strategy.value] = by_strategy.get(r.window_strategy.value, 0) + 1
        breaching_count = sum(
            1
            for r in self._records
            if r.compliance_status in (ComplianceStatus.BREACHING, ComplianceStatus.BREACHED)
        )
        pcts = [r.compliance_pct for r in self._records]
        avg_compliance_pct = round(sum(pcts) / len(pcts), 2) if pcts else 0.0
        rankings = self.rank_by_compliance()
        top_breaching = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if breaching_count > 0:
            recs.append(
                f"{breaching_count} SLO window(s) breaching"
                f" (min compliance {self._min_compliance_pct}%)"
            )
        at_risk = sum(1 for r in self._records if r.compliance_status == ComplianceStatus.AT_RISK)
        if at_risk > 0:
            recs.append(f"{at_risk} SLO window(s) at risk — monitor closely")
        if not recs:
            recs.append("SLO window compliance is acceptable")
        return SLOWindowReport(
            total_records=len(self._records),
            total_evaluations=len(self._metrics),
            breaching_count=breaching_count,
            avg_compliance_pct=avg_compliance_pct,
            by_duration=by_duration,
            by_status=by_status,
            by_strategy=by_strategy,
            top_breaching=top_breaching,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("slo_window.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dur_dist: dict[str, int] = {}
        for r in self._records:
            key = r.window_duration.value
            dur_dist[key] = dur_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_compliance_pct": self._min_compliance_pct,
            "duration_distribution": dur_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
