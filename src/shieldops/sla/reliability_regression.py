"""Reliability Regression Detector — detect reliability regressions correlated with changes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RegressionSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    COSMETIC = "cosmetic"
    NONE = "none"


class RegressionType(StrEnum):
    ERROR_RATE = "error_rate"
    LATENCY = "latency"
    AVAILABILITY = "availability"
    THROUGHPUT = "throughput"
    SATURATION = "saturation"


class CorrelationStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    COINCIDENTAL = "coincidental"
    UNKNOWN = "unknown"


# --- Models ---


class RegressionEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    change_id: str = ""
    regression_type: RegressionType = RegressionType.ERROR_RATE
    severity: RegressionSeverity = RegressionSeverity.MINOR
    baseline_value: float = 0.0
    current_value: float = 0.0
    deviation_pct: float = 0.0
    correlation: CorrelationStrength = CorrelationStrength.UNKNOWN
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RegressionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    total_regressions: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    avg_deviation_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ReliabilityRegressionReport(BaseModel):
    total_regressions: int = 0
    total_analyses: int = 0
    avg_deviation_pct: float = 0.0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ReliabilityRegressionDetector:
    """Detect reliability regressions correlated with specific changes."""

    def __init__(
        self,
        max_records: int = 200000,
        deviation_threshold_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._deviation_threshold_pct = deviation_threshold_pct
        self._records: list[RegressionEvent] = []
        self._analyses: list[RegressionAnalysis] = []
        logger.info(
            "reliability_regression.initialized",
            max_records=max_records,
            deviation_threshold_pct=deviation_threshold_pct,
        )

    # -- internal helpers ------------------------------------------------

    def _deviation_to_severity(self, deviation_pct: float) -> RegressionSeverity:
        if deviation_pct >= 50:
            return RegressionSeverity.CRITICAL
        if deviation_pct >= 25:
            return RegressionSeverity.MAJOR
        if deviation_pct >= self._deviation_threshold_pct:
            return RegressionSeverity.MINOR
        if deviation_pct >= 5:
            return RegressionSeverity.COSMETIC
        return RegressionSeverity.NONE

    # -- record / get / list ---------------------------------------------

    def record_regression(
        self,
        service: str,
        change_id: str = "",
        regression_type: RegressionType = RegressionType.ERROR_RATE,
        severity: RegressionSeverity | None = None,
        baseline_value: float = 0.0,
        current_value: float = 0.0,
        deviation_pct: float = 0.0,
        correlation: CorrelationStrength = CorrelationStrength.UNKNOWN,
        details: str = "",
    ) -> RegressionEvent:
        if severity is None:
            severity = self._deviation_to_severity(deviation_pct)
        record = RegressionEvent(
            service=service,
            change_id=change_id,
            regression_type=regression_type,
            severity=severity,
            baseline_value=baseline_value,
            current_value=current_value,
            deviation_pct=deviation_pct,
            correlation=correlation,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "reliability_regression.recorded",
            record_id=record.id,
            service=service,
            regression_type=regression_type.value,
            deviation_pct=deviation_pct,
        )
        return record

    def get_regression(self, record_id: str) -> RegressionEvent | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_regressions(
        self,
        service: str | None = None,
        regression_type: RegressionType | None = None,
        severity: RegressionSeverity | None = None,
        limit: int = 50,
    ) -> list[RegressionEvent]:
        results = list(self._records)
        if service is not None:
            results = [r for r in results if r.service == service]
        if regression_type is not None:
            results = [r for r in results if r.regression_type == regression_type]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def detect_regressions_for_change(self, change_id: str) -> list[dict[str, Any]]:
        """Find all regressions linked to a specific change."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.change_id == change_id:
                results.append(
                    {
                        "service": r.service,
                        "regression_type": r.regression_type.value,
                        "severity": r.severity.value,
                        "deviation_pct": r.deviation_pct,
                        "correlation": r.correlation.value,
                    }
                )
        results.sort(key=lambda x: x["deviation_pct"], reverse=True)
        return results

    def analyze_service_regressions(self, service: str) -> dict[str, Any]:
        """Analyze regression history for a service."""
        svc_records = [r for r in self._records if r.service == service]
        if not svc_records:
            return {"service": service, "total_regressions": 0}
        by_type: dict[str, int] = {}
        for r in svc_records:
            by_type[r.regression_type.value] = by_type.get(r.regression_type.value, 0) + 1
        avg_dev = round(sum(r.deviation_pct for r in svc_records) / len(svc_records), 2)
        return {
            "service": service,
            "total_regressions": len(svc_records),
            "by_type": by_type,
            "avg_deviation_pct": avg_dev,
        }

    def identify_regression_prone_services(self) -> list[dict[str, Any]]:
        """Rank services by regression frequency."""
        svc_counts: dict[str, int] = {}
        svc_deviations: dict[str, list[float]] = {}
        for r in self._records:
            svc_counts[r.service] = svc_counts.get(r.service, 0) + 1
            svc_deviations.setdefault(r.service, []).append(r.deviation_pct)
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            devs = svc_deviations[svc]
            avg_dev = round(sum(devs) / len(devs), 2)
            results.append(
                {
                    "service": svc,
                    "regression_count": count,
                    "avg_deviation_pct": avg_dev,
                }
            )
        results.sort(key=lambda x: x["regression_count"], reverse=True)
        return results

    def correlate_with_changes(self) -> list[dict[str, Any]]:
        """Group regressions by change ID to identify problematic changes."""
        change_map: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            if r.change_id:
                change_map.setdefault(r.change_id, []).append(
                    {
                        "service": r.service,
                        "type": r.regression_type.value,
                        "severity": r.severity.value,
                        "deviation_pct": r.deviation_pct,
                    }
                )
        results: list[dict[str, Any]] = []
        for change_id, regressions in change_map.items():
            results.append(
                {
                    "change_id": change_id,
                    "regression_count": len(regressions),
                    "regressions": regressions,
                }
            )
        results.sort(key=lambda x: x["regression_count"], reverse=True)
        return results

    def calculate_regression_rate(self) -> dict[str, Any]:
        """Calculate overall regression rate metrics."""
        if not self._records:
            return {"total": 0, "critical_rate_pct": 0.0, "avg_deviation_pct": 0.0}
        critical = sum(1 for r in self._records if r.severity == RegressionSeverity.CRITICAL)
        avg_dev = round(
            sum(r.deviation_pct for r in self._records) / len(self._records),
            2,
        )
        return {
            "total": len(self._records),
            "critical_count": critical,
            "critical_rate_pct": round((critical / len(self._records)) * 100, 2),
            "avg_deviation_pct": avg_dev,
        }

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ReliabilityRegressionReport:
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in self._records:
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
            by_type[r.regression_type.value] = by_type.get(r.regression_type.value, 0) + 1
        avg_dev = (
            round(
                sum(r.deviation_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        critical = sum(1 for r in self._records if r.severity == RegressionSeverity.CRITICAL)
        recs: list[str] = []
        if critical > 0:
            recs.append(f"{critical} critical regression(s) detected")
        high_dev = sum(1 for r in self._records if r.deviation_pct >= self._deviation_threshold_pct)
        if high_dev > 0:
            recs.append(
                f"{high_dev} regression(s) exceed {self._deviation_threshold_pct}% "
                "deviation threshold"
            )
        if not recs:
            recs.append("No significant reliability regressions detected")
        return ReliabilityRegressionReport(
            total_regressions=len(self._records),
            total_analyses=len(self._analyses),
            avg_deviation_pct=avg_dev,
            by_severity=by_severity,
            by_type=by_type,
            critical_count=critical,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("reliability_regression.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        severity_dist: dict[str, int] = {}
        for r in self._records:
            key = r.severity.value
            severity_dist[key] = severity_dist.get(key, 0) + 1
        return {
            "total_regressions": len(self._records),
            "deviation_threshold_pct": self._deviation_threshold_pct,
            "severity_distribution": severity_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_changes": len({r.change_id for r in self._records if r.change_id}),
        }
