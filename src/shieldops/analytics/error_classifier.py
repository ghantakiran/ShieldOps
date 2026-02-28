"""Error Pattern Classifier — classify and analyze error patterns across services."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ErrorCategory(StrEnum):
    TIMEOUT = "timeout"
    CONNECTION_FAILURE = "connection_failure"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    INTERNAL_ERROR = "internal_error"


class ErrorSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class PatternType(StrEnum):
    RECURRING = "recurring"
    SPORADIC = "sporadic"
    BURST = "burst"
    CASCADING = "cascading"
    ISOLATED = "isolated"


# --- Models ---


class ErrorRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    service_name: str = ""
    error_category: ErrorCategory = ErrorCategory.INTERNAL_ERROR
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    error_code: str = ""
    message: str = ""
    occurrence_count: int = 1
    created_at: float = Field(default_factory=time.time)


class ErrorPattern(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    pattern_name: str = ""
    pattern_type: PatternType = PatternType.ISOLATED
    error_category: ErrorCategory = ErrorCategory.INTERNAL_ERROR
    frequency_per_hour: float = 0.0
    affected_services: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class ErrorClassifierReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_errors: int = 0
    total_patterns: int = 0
    error_rate_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recurring_pattern_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ErrorPatternClassifier:
    """Classify and analyze error patterns across services."""

    def __init__(
        self,
        max_records: int = 200000,
        max_error_rate_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_error_rate_pct = max_error_rate_pct
        self._records: list[ErrorRecord] = []
        self._patterns: list[ErrorPattern] = []
        logger.info(
            "error_classifier.initialized",
            max_records=max_records,
            max_error_rate_pct=max_error_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_error(
        self,
        service_name: str,
        error_category: ErrorCategory = ErrorCategory.INTERNAL_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        error_code: str = "",
        message: str = "",
        occurrence_count: int = 1,
    ) -> ErrorRecord:
        record = ErrorRecord(
            service_name=service_name,
            error_category=error_category,
            severity=severity,
            error_code=error_code,
            message=message,
            occurrence_count=occurrence_count,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "error_classifier.error_recorded",
            record_id=record.id,
            service_name=service_name,
            error_category=error_category.value,
            severity=severity.value,
        )
        return record

    def get_error(self, record_id: str) -> ErrorRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_errors(
        self,
        service_name: str | None = None,
        error_category: ErrorCategory | None = None,
        limit: int = 50,
    ) -> list[ErrorRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if error_category is not None:
            results = [r for r in results if r.error_category == error_category]
        return results[-limit:]

    def add_pattern(
        self,
        pattern_name: str,
        pattern_type: PatternType = PatternType.ISOLATED,
        error_category: ErrorCategory = ErrorCategory.INTERNAL_ERROR,
        frequency_per_hour: float = 0.0,
        affected_services: list[str] | None = None,
    ) -> ErrorPattern:
        pattern = ErrorPattern(
            pattern_name=pattern_name,
            pattern_type=pattern_type,
            error_category=error_category,
            frequency_per_hour=frequency_per_hour,
            affected_services=affected_services or [],
        )
        self._patterns.append(pattern)
        if len(self._patterns) > self._max_records:
            self._patterns = self._patterns[-self._max_records :]
        logger.info(
            "error_classifier.pattern_added",
            pattern_name=pattern_name,
            pattern_type=pattern_type.value,
            error_category=error_category.value,
        )
        return pattern

    # -- domain operations -----------------------------------------------

    def analyze_error_distribution(self, service_name: str) -> dict[str, Any]:
        """Analyze error category distribution for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        category_dist: dict[str, int] = {}
        total_occurrences = 0
        for r in records:
            category_dist[r.error_category.value] = (
                category_dist.get(r.error_category.value, 0) + r.occurrence_count
            )
            total_occurrences += r.occurrence_count
        return {
            "service_name": service_name,
            "record_count": len(records),
            "total_occurrences": total_occurrences,
            "category_distribution": category_dist,
        }

    def identify_recurring_patterns(self) -> list[dict[str, Any]]:
        """Find services with more than 3 error records (recurring)."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "error_count": count,
                        "pattern_type": PatternType.RECURRING.value,
                    }
                )
        results.sort(key=lambda x: x["error_count"], reverse=True)
        return results

    def rank_by_frequency(self) -> list[dict[str, Any]]:
        """Rank services by total occurrence count descending."""
        svc_occurrences: dict[str, int] = {}
        for r in self._records:
            svc_occurrences[r.service_name] = (
                svc_occurrences.get(r.service_name, 0) + r.occurrence_count
            )
        results: list[dict[str, Any]] = []
        for svc, total in svc_occurrences.items():
            results.append({"service_name": svc, "total_occurrences": total})
        results.sort(key=lambda x: x["total_occurrences"], reverse=True)
        return results

    def detect_error_trends(self) -> list[dict[str, Any]]:
        """Detect services with CRITICAL or HIGH severity errors more than once."""
        crit_counts: dict[str, int] = {}
        for r in self._records:
            if r.severity in (ErrorSeverity.CRITICAL, ErrorSeverity.HIGH):
                crit_counts[r.service_name] = crit_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in crit_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "high_severity_count": count,
                        "trend": "escalating",
                    }
                )
        results.sort(key=lambda x: x["high_severity_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ErrorClassifierReport:
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        total_occurrences = 0
        for r in self._records:
            by_category[r.error_category.value] = by_category.get(r.error_category.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
            total_occurrences += r.occurrence_count
        critical_count = sum(1 for r in self._records if r.severity == ErrorSeverity.CRITICAL)
        recurring_count = len(self.identify_recurring_patterns())
        error_rate = round(critical_count / len(self._records) * 100, 2) if self._records else 0.0
        recs: list[str] = []
        if error_rate > self._max_error_rate_pct:
            recs.append(f"Error rate {error_rate}% exceeds threshold {self._max_error_rate_pct}%")
        if critical_count > 0:
            recs.append(f"{critical_count} critical error record(s) require immediate attention")
        if recurring_count > 0:
            recs.append(f"{recurring_count} service(s) with recurring error patterns detected")
        if not recs:
            recs.append("Error pattern classification meets targets")
        return ErrorClassifierReport(
            total_errors=len(self._records),
            total_patterns=len(self._patterns),
            error_rate_pct=error_rate,
            by_category=by_category,
            by_severity=by_severity,
            critical_count=critical_count,
            recurring_pattern_count=recurring_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._patterns.clear()
        logger.info("error_classifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.error_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_errors": len(self._records),
            "total_patterns": len(self._patterns),
            "max_error_rate_pct": self._max_error_rate_pct,
            "category_distribution": category_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
