"""Observability Gap Detector — identify gaps in observability coverage across services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GapType(StrEnum):
    MISSING_METRICS = "missing_metrics"
    MISSING_TRACES = "missing_traces"
    MISSING_LOGS = "missing_logs"
    MISSING_ALERTS = "missing_alerts"
    MISSING_DASHBOARDS = "missing_dashboards"


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFORMATIONAL = "informational"


class CoverageLevel(StrEnum):
    FULL = "full"
    HIGH = "high"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


# --- Models ---


class GapRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    gap_type: GapType = GapType.MISSING_METRICS
    severity: GapSeverity = GapSeverity.MODERATE
    coverage: CoverageLevel = CoverageLevel.PARTIAL
    coverage_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CoverageAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_name: str = ""
    gap_type: GapType = GapType.MISSING_METRICS
    severity: GapSeverity = GapSeverity.MODERATE
    target_coverage_pct: float = 80.0
    review_interval_days: int = 30
    created_at: float = Field(default_factory=time.time)


class ObservabilityGapReport(BaseModel):
    total_gaps: int = 0
    total_assessments: int = 0
    coverage_rate_pct: float = 0.0
    by_gap_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ObservabilityGapDetector:
    """Identify gaps in observability coverage across services."""

    def __init__(
        self,
        max_records: int = 200000,
        min_coverage_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_coverage_pct = min_coverage_pct
        self._records: list[GapRecord] = []
        self._assessments: list[CoverageAssessment] = []
        logger.info(
            "observability_gap.initialized",
            max_records=max_records,
            min_coverage_pct=min_coverage_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_gap(
        self,
        service_name: str,
        gap_type: GapType = GapType.MISSING_METRICS,
        severity: GapSeverity = GapSeverity.MODERATE,
        coverage: CoverageLevel = CoverageLevel.PARTIAL,
        coverage_pct: float = 0.0,
        details: str = "",
    ) -> GapRecord:
        record = GapRecord(
            service_name=service_name,
            gap_type=gap_type,
            severity=severity,
            coverage=coverage,
            coverage_pct=coverage_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "observability_gap.gap_recorded",
            record_id=record.id,
            service_name=service_name,
            gap_type=gap_type.value,
            severity=severity.value,
        )
        return record

    def get_gap(self, record_id: str) -> GapRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_gaps(
        self,
        service_name: str | None = None,
        gap_type: GapType | None = None,
        limit: int = 50,
    ) -> list[GapRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if gap_type is not None:
            results = [r for r in results if r.gap_type == gap_type]
        return results[-limit:]

    def add_assessment(
        self,
        assessment_name: str,
        gap_type: GapType = GapType.MISSING_METRICS,
        severity: GapSeverity = GapSeverity.MODERATE,
        target_coverage_pct: float = 80.0,
        review_interval_days: int = 30,
    ) -> CoverageAssessment:
        assessment = CoverageAssessment(
            assessment_name=assessment_name,
            gap_type=gap_type,
            severity=severity,
            target_coverage_pct=target_coverage_pct,
            review_interval_days=review_interval_days,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "observability_gap.assessment_added",
            assessment_name=assessment_name,
            gap_type=gap_type.value,
            severity=severity.value,
        )
        return assessment

    # -- domain operations -----------------------------------------------

    def analyze_coverage_gaps(self, service_name: str) -> dict[str, Any]:
        """Analyze coverage gaps for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_coverage = round(sum(r.coverage_pct for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "avg_coverage": avg_coverage,
            "record_count": len(records),
            "meets_threshold": avg_coverage >= self._min_coverage_pct,
        }

    def identify_critical_gaps(self) -> list[dict[str, Any]]:
        """Find services with >1 CRITICAL/HIGH gap."""
        crit_counts: dict[str, int] = {}
        for r in self._records:
            if r.severity in (GapSeverity.CRITICAL, GapSeverity.HIGH):
                crit_counts[r.service_name] = crit_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in crit_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "critical_count": count,
                    }
                )
        results.sort(key=lambda x: x["critical_count"], reverse=True)
        return results

    def rank_by_gap_severity(self) -> list[dict[str, Any]]:
        """Rank services by average coverage_pct ascending (worst first)."""
        svc_coverage: dict[str, list[float]] = {}
        for r in self._records:
            svc_coverage.setdefault(r.service_name, []).append(r.coverage_pct)
        results: list[dict[str, Any]] = []
        for svc, coverages in svc_coverage.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_coverage_pct": round(sum(coverages) / len(coverages), 2),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_pct"])
        return results

    def detect_coverage_trends(self) -> list[dict[str, Any]]:
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

    def generate_report(self) -> ObservabilityGapReport:
        by_gap_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_gap_type[r.gap_type.value] = by_gap_type.get(r.gap_type.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
        covered_count = sum(
            1 for r in self._records if r.coverage in (CoverageLevel.FULL, CoverageLevel.HIGH)
        )
        coverage_rate = round(covered_count / len(self._records) * 100, 2) if self._records else 0.0
        critical_count = sum(1 for r in self._records if r.severity == GapSeverity.CRITICAL)
        critical_gaps = len(self.identify_critical_gaps())
        recs: list[str] = []
        if self._records and coverage_rate < self._min_coverage_pct:
            recs.append(
                f"Coverage rate {coverage_rate}% is below {self._min_coverage_pct}% threshold"
            )
        if critical_gaps > 0:
            recs.append(f"{critical_gaps} service(s) with critical gaps")
        if critical_count > 0:
            recs.append(f"{critical_count} critical gap record(s) detected")
        if not recs:
            recs.append("Observability coverage meets targets")
        return ObservabilityGapReport(
            total_gaps=len(self._records),
            total_assessments=len(self._assessments),
            coverage_rate_pct=coverage_rate,
            by_gap_type=by_gap_type,
            by_severity=by_severity,
            critical_count=critical_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("observability_gap.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        gap_type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.gap_type.value
            gap_type_dist[key] = gap_type_dist.get(key, 0) + 1
        return {
            "total_gaps": len(self._records),
            "total_assessments": len(self._assessments),
            "min_coverage_pct": self._min_coverage_pct,
            "gap_type_distribution": gap_type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
