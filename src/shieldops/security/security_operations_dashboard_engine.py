"""Security Operations Dashboard Engine — real-time SOC dashboard metrics engine."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AlertSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnalystTier(StrEnum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    LEAD = "lead"


class MetricCategory(StrEnum):
    MTTD = "mttd"
    MTTR = "mttr"
    ALERT_VOLUME = "alert_volume"
    FALSE_POSITIVE_RATE = "false_positive_rate"
    ESCALATION_RATE = "escalation_rate"


# --- Models ---


class SOCMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: MetricCategory = MetricCategory.MTTD
    value: float = 0.0
    severity: AlertSeverity = AlertSeverity.MEDIUM
    analyst_id: str = ""
    tier: AnalystTier = AnalystTier.TIER_1
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponseTimeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    severity: AlertSeverity = AlertSeverity.MEDIUM
    detection_time_ms: float = 0.0
    response_time_ms: float = 0.0
    resolution_time_ms: float = 0.0
    analyst_id: str = ""
    created_at: float = Field(default_factory=time.time)


class DashboardReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_metrics: int = 0
    total_responses: int = 0
    avg_mttd: float = 0.0
    avg_mttr: float = 0.0
    alert_volume: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    top_issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityOperationsDashboardEngine:
    """Real-time SOC dashboard metrics engine."""

    def __init__(
        self,
        max_records: int = 200000,
        mttd_threshold_ms: float = 60000.0,
        mttr_threshold_ms: float = 300000.0,
    ) -> None:
        self._max_records = max_records
        self._mttd_threshold = mttd_threshold_ms
        self._mttr_threshold = mttr_threshold_ms
        self._metrics: list[SOCMetric] = []
        self._responses: list[ResponseTimeRecord] = []
        logger.info(
            "security_operations_dashboard_engine.initialized",
            max_records=max_records,
            mttd_threshold_ms=mttd_threshold_ms,
            mttr_threshold_ms=mttr_threshold_ms,
        )

    def compute_soc_metrics(
        self,
        category: MetricCategory = MetricCategory.MTTD,
        value: float = 0.0,
        severity: AlertSeverity = AlertSeverity.MEDIUM,
        analyst_id: str = "",
        tier: AnalystTier = AnalystTier.TIER_1,
        service: str = "",
        team: str = "",
    ) -> SOCMetric:
        """Compute and record a SOC metric."""
        metric = SOCMetric(
            category=category,
            value=value,
            severity=severity,
            analyst_id=analyst_id,
            tier=tier,
            service=service,
            team=team,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "security_operations_dashboard_engine.metric_computed",
            metric_id=metric.id,
            category=category.value,
            value=value,
        )
        return metric

    def track_response_times(
        self,
        alert_id: str,
        severity: AlertSeverity = AlertSeverity.MEDIUM,
        detection_time_ms: float = 0.0,
        response_time_ms: float = 0.0,
        resolution_time_ms: float = 0.0,
        analyst_id: str = "",
    ) -> ResponseTimeRecord:
        """Track response times for an alert."""
        record = ResponseTimeRecord(
            alert_id=alert_id,
            severity=severity,
            detection_time_ms=detection_time_ms,
            response_time_ms=response_time_ms,
            resolution_time_ms=resolution_time_ms,
            analyst_id=analyst_id,
        )
        self._responses.append(record)
        if len(self._responses) > self._max_records:
            self._responses = self._responses[-self._max_records :]
        logger.info(
            "security_operations_dashboard_engine.response_tracked",
            record_id=record.id,
            alert_id=alert_id,
        )
        return record

    def analyze_alert_volume(self) -> dict[str, Any]:
        """Analyze alert volume by severity and time."""
        if not self._responses:
            return {"total": 0, "by_severity": {}}
        by_sev: dict[str, int] = {}
        for r in self._responses:
            by_sev[r.severity.value] = by_sev.get(r.severity.value, 0) + 1
        return {
            "total": len(self._responses),
            "by_severity": by_sev,
        }

    def score_analyst_performance(self, analyst_id: str) -> dict[str, Any]:
        """Score an analyst's performance based on response metrics."""
        analyst_responses = [r for r in self._responses if r.analyst_id == analyst_id]
        if not analyst_responses:
            return {"analyst_id": analyst_id, "score": 0.0, "alerts_handled": 0}
        det_times = [r.detection_time_ms for r in analyst_responses]
        resp_times = [r.response_time_ms for r in analyst_responses]
        avg_det = sum(det_times) / len(det_times)
        avg_resp = sum(resp_times) / len(resp_times)
        det_score = max(0, 100 - (avg_det / self._mttd_threshold * 100))
        resp_score = max(0, 100 - (avg_resp / self._mttr_threshold * 100))
        overall = round((det_score + resp_score) / 2, 2)
        return {
            "analyst_id": analyst_id,
            "score": overall,
            "alerts_handled": len(analyst_responses),
            "avg_detection_ms": round(avg_det, 2),
            "avg_response_ms": round(avg_resp, 2),
        }

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get aggregated dashboard data."""
        det_times = [r.detection_time_ms for r in self._responses]
        resp_times = [r.response_time_ms for r in self._responses]
        avg_mttd = round(sum(det_times) / len(det_times), 2) if det_times else 0.0
        avg_mttr = round(sum(resp_times) / len(resp_times), 2) if resp_times else 0.0
        by_sev: dict[str, int] = {}
        for r in self._responses:
            by_sev[r.severity.value] = by_sev.get(r.severity.value, 0) + 1
        by_cat: dict[str, int] = {}
        for m in self._metrics:
            by_cat[m.category.value] = by_cat.get(m.category.value, 0) + 1
        breaches: list[str] = []
        if avg_mttd > self._mttd_threshold:
            breaches.append(f"MTTD {avg_mttd}ms exceeds threshold {self._mttd_threshold}ms")
        if avg_mttr > self._mttr_threshold:
            breaches.append(f"MTTR {avg_mttr}ms exceeds threshold {self._mttr_threshold}ms")
        return {
            "avg_mttd": avg_mttd,
            "avg_mttr": avg_mttr,
            "total_alerts": len(self._responses),
            "total_metrics": len(self._metrics),
            "by_severity": by_sev,
            "by_category": by_cat,
            "sla_breaches": breaches,
        }

    def generate_report(self) -> DashboardReport:
        """Generate a comprehensive dashboard report."""
        by_sev: dict[str, int] = {}
        for r in self._responses:
            by_sev[r.severity.value] = by_sev.get(r.severity.value, 0) + 1
        by_cat: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        for m in self._metrics:
            by_cat[m.category.value] = by_cat.get(m.category.value, 0) + 1
            by_tier[m.tier.value] = by_tier.get(m.tier.value, 0) + 1
        det_times = [r.detection_time_ms for r in self._responses]
        resp_times = [r.response_time_ms for r in self._responses]
        avg_mttd = round(sum(det_times) / len(det_times), 2) if det_times else 0.0
        avg_mttr = round(sum(resp_times) / len(resp_times), 2) if resp_times else 0.0
        issues: list[str] = []
        if avg_mttd > self._mttd_threshold:
            issues.append("MTTD exceeds threshold")
        if avg_mttr > self._mttr_threshold:
            issues.append("MTTR exceeds threshold")
        recs: list[str] = []
        if issues:
            recs.extend(issues)
        if not recs:
            recs.append("SOC metrics within healthy range")
        return DashboardReport(
            total_metrics=len(self._metrics),
            total_responses=len(self._responses),
            avg_mttd=avg_mttd,
            avg_mttr=avg_mttr,
            alert_volume=len(self._responses),
            by_severity=by_sev,
            by_category=by_cat,
            by_tier=by_tier,
            top_issues=issues,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        dist: dict[str, int] = {}
        for m in self._metrics:
            key = m.category.value
            dist[key] = dist.get(key, 0) + 1
        return {
            "total_metrics": len(self._metrics),
            "total_responses": len(self._responses),
            "mttd_threshold": self._mttd_threshold,
            "mttr_threshold": self._mttr_threshold,
            "category_distribution": dist,
            "unique_analysts": len({r.analyst_id for r in self._responses}),
        }

    def clear_data(self) -> dict[str, str]:
        """Clear all stored data."""
        self._metrics.clear()
        self._responses.clear()
        logger.info("security_operations_dashboard_engine.cleared")
        return {"status": "cleared"}
