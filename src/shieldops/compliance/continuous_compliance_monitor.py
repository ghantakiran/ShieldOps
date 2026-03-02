"""Continuous Compliance Monitor — real-time compliance drift across frameworks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class Framework(StrEnum):
    SOC2 = "soc2"
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    NIST_CSF = "nist_csf"


class DriftSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class MonitoringFrequency(StrEnum):
    REAL_TIME = "real_time"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# --- Models ---


class ComplianceMonitorRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    framework: Framework = Framework.SOC2
    drift_severity: DriftSeverity = DriftSeverity.CRITICAL
    monitoring_frequency: MonitoringFrequency = MonitoringFrequency.REAL_TIME
    compliance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceMonitorAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_name: str = ""
    framework: Framework = Framework.SOC2
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceMonitorReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_compliance_count: int = 0
    avg_compliance_score: float = 0.0
    by_framework: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    top_low_compliance: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ContinuousComplianceMonitor:
    """Real-time compliance drift monitoring across SOC2, GDPR, HIPAA, PCI, NIST."""

    def __init__(
        self,
        max_records: int = 200000,
        compliance_drift_threshold: float = 85.0,
    ) -> None:
        self._max_records = max_records
        self._compliance_drift_threshold = compliance_drift_threshold
        self._records: list[ComplianceMonitorRecord] = []
        self._analyses: list[ComplianceMonitorAnalysis] = []
        logger.info(
            "continuous_compliance_monitor.initialized",
            max_records=max_records,
            compliance_drift_threshold=compliance_drift_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_control(
        self,
        control_name: str,
        framework: Framework = Framework.SOC2,
        drift_severity: DriftSeverity = DriftSeverity.CRITICAL,
        monitoring_frequency: MonitoringFrequency = MonitoringFrequency.REAL_TIME,
        compliance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ComplianceMonitorRecord:
        record = ComplianceMonitorRecord(
            control_name=control_name,
            framework=framework,
            drift_severity=drift_severity,
            monitoring_frequency=monitoring_frequency,
            compliance_score=compliance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "continuous_compliance_monitor.control_recorded",
            record_id=record.id,
            control_name=control_name,
            framework=framework.value,
            drift_severity=drift_severity.value,
        )
        return record

    def get_control(self, record_id: str) -> ComplianceMonitorRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_controls(
        self,
        framework: Framework | None = None,
        drift_severity: DriftSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ComplianceMonitorRecord]:
        results = list(self._records)
        if framework is not None:
            results = [r for r in results if r.framework == framework]
        if drift_severity is not None:
            results = [r for r in results if r.drift_severity == drift_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        control_name: str,
        framework: Framework = Framework.SOC2,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ComplianceMonitorAnalysis:
        analysis = ComplianceMonitorAnalysis(
            control_name=control_name,
            framework=framework,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "continuous_compliance_monitor.analysis_added",
            control_name=control_name,
            framework=framework.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_framework_distribution(self) -> dict[str, Any]:
        """Group by framework; return count and avg compliance_score."""
        fw_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.framework.value
            fw_data.setdefault(key, []).append(r.compliance_score)
        result: dict[str, Any] = {}
        for fw, scores in fw_data.items():
            result[fw] = {
                "count": len(scores),
                "avg_compliance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_compliance_controls(self) -> list[dict[str, Any]]:
        """Return records where compliance_score < compliance_drift_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.compliance_score < self._compliance_drift_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "control_name": r.control_name,
                        "framework": r.framework.value,
                        "compliance_score": r.compliance_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["compliance_score"])

    def rank_by_compliance_score(self) -> list[dict[str, Any]]:
        """Group by service, avg compliance_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.compliance_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_compliance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_compliance_score"])
        return results

    def detect_compliance_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> ComplianceMonitorReport:
        by_framework: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_frequency: dict[str, int] = {}
        for r in self._records:
            by_framework[r.framework.value] = by_framework.get(r.framework.value, 0) + 1
            by_severity[r.drift_severity.value] = by_severity.get(r.drift_severity.value, 0) + 1
            by_frequency[r.monitoring_frequency.value] = (
                by_frequency.get(r.monitoring_frequency.value, 0) + 1
            )
        low_compliance_count = sum(
            1 for r in self._records if r.compliance_score < self._compliance_drift_threshold
        )
        scores = [r.compliance_score for r in self._records]
        avg_compliance_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_compliance_controls()
        top_low_compliance = [o["control_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_compliance_count > 0:
            recs.append(
                f"{low_compliance_count} control(s) below compliance threshold "
                f"({self._compliance_drift_threshold})"
            )
        if self._records and avg_compliance_score < self._compliance_drift_threshold:
            recs.append(
                f"Avg compliance score {avg_compliance_score} below threshold "
                f"({self._compliance_drift_threshold})"
            )
        if not recs:
            recs.append("Continuous compliance monitoring is healthy")
        return ComplianceMonitorReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_compliance_count=low_compliance_count,
            avg_compliance_score=avg_compliance_score,
            by_framework=by_framework,
            by_severity=by_severity,
            by_frequency=by_frequency,
            top_low_compliance=top_low_compliance,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("continuous_compliance_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        framework_dist: dict[str, int] = {}
        for r in self._records:
            key = r.framework.value
            framework_dist[key] = framework_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "compliance_drift_threshold": self._compliance_drift_threshold,
            "framework_distribution": framework_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
