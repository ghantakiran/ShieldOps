"""Deployment Rollback Analyzer — analyze rollback patterns and frequency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RollbackReason(StrEnum):
    PERFORMANCE_DEGRADATION = "performance_degradation"
    ERROR_SPIKE = "error_spike"
    HEALTH_CHECK_FAILURE = "health_check_failure"
    CUSTOMER_IMPACT = "customer_impact"
    MANUAL_TRIGGER = "manual_trigger"


class RollbackImpact(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


class RollbackSpeed(StrEnum):
    INSTANT = "instant"
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"
    MANUAL = "manual"


# --- Models ---


class RollbackRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    reason: RollbackReason = RollbackReason.MANUAL_TRIGGER
    impact: RollbackImpact = RollbackImpact.LOW
    speed: RollbackSpeed = RollbackSpeed.NORMAL
    rollback_rate_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RollbackPattern(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_name: str = ""
    reason: RollbackReason = RollbackReason.MANUAL_TRIGGER
    impact: RollbackImpact = RollbackImpact.LOW
    frequency: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RollbackAnalyzerReport(BaseModel):
    total_rollbacks: int = 0
    total_patterns: int = 0
    avg_rollback_rate_pct: float = 0.0
    by_reason: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    high_rollback_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentRollbackAnalyzer:
    """Analyze rollback patterns, frequency, and high-impact services."""

    def __init__(
        self,
        max_records: int = 200000,
        max_rate_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_rate_pct = max_rate_pct
        self._records: list[RollbackRecord] = []
        self._patterns: list[RollbackPattern] = []
        logger.info(
            "rollback_analyzer.initialized",
            max_records=max_records,
            max_rate_pct=max_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_rollback(
        self,
        service_name: str,
        reason: RollbackReason = RollbackReason.MANUAL_TRIGGER,
        impact: RollbackImpact = RollbackImpact.LOW,
        speed: RollbackSpeed = RollbackSpeed.NORMAL,
        rollback_rate_pct: float = 0.0,
        details: str = "",
    ) -> RollbackRecord:
        record = RollbackRecord(
            service_name=service_name,
            reason=reason,
            impact=impact,
            speed=speed,
            rollback_rate_pct=rollback_rate_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "rollback_analyzer.rollback_recorded",
            record_id=record.id,
            service_name=service_name,
            reason=reason.value,
            impact=impact.value,
        )
        return record

    def get_rollback(self, record_id: str) -> RollbackRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_rollbacks(
        self,
        service_name: str | None = None,
        reason: RollbackReason | None = None,
        limit: int = 50,
    ) -> list[RollbackRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if reason is not None:
            results = [r for r in results if r.reason == reason]
        return results[-limit:]

    def add_pattern(
        self,
        pattern_name: str,
        reason: RollbackReason = RollbackReason.MANUAL_TRIGGER,
        impact: RollbackImpact = RollbackImpact.LOW,
        frequency: int = 0,
        description: str = "",
    ) -> RollbackPattern:
        pattern = RollbackPattern(
            pattern_name=pattern_name,
            reason=reason,
            impact=impact,
            frequency=frequency,
            description=description,
        )
        self._patterns.append(pattern)
        if len(self._patterns) > self._max_records:
            self._patterns = self._patterns[-self._max_records :]
        logger.info(
            "rollback_analyzer.pattern_added",
            pattern_id=pattern.id,
            pattern_name=pattern_name,
            reason=reason.value,
        )
        return pattern

    # -- domain operations -----------------------------------------------

    def analyze_rollback_frequency(self, service_name: str) -> dict[str, Any]:
        """Analyze rollback frequency for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_rate = round(sum(r.rollback_rate_pct for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "total": len(records),
            "avg_rate": avg_rate,
            "meets_threshold": avg_rate <= self._max_rate_pct,
        }

    def identify_high_rollback_services(self) -> list[dict[str, Any]]:
        """Find services with >1 CRITICAL or HIGH impact rollbacks, sorted desc."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.impact in (RollbackImpact.CRITICAL, RollbackImpact.HIGH):
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 1:
                results.append({"service_name": svc, "high_impact_count": count})
        results.sort(key=lambda x: x["high_impact_count"], reverse=True)
        return results

    def rank_by_rollback_rate(self) -> list[dict[str, Any]]:
        """Average rollback rate per service, sorted desc."""
        svc_rates: dict[str, list[float]] = {}
        for r in self._records:
            svc_rates.setdefault(r.service_name, []).append(r.rollback_rate_pct)
        results: list[dict[str, Any]] = []
        for svc, rates in svc_rates.items():
            avg = round(sum(rates) / len(rates), 2)
            results.append({"service_name": svc, "avg_rollback_rate_pct": avg})
        results.sort(key=lambda x: x["avg_rollback_rate_pct"], reverse=True)
        return results

    def detect_rollback_trends(self) -> list[dict[str, Any]]:
        """Detect services with >3 rollback records (trending)."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append({"service_name": svc, "rollback_count": count})
        results.sort(key=lambda x: x["rollback_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> RollbackAnalyzerReport:
        by_reason: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        for r in self._records:
            by_reason[r.reason.value] = by_reason.get(r.reason.value, 0) + 1
            by_impact[r.impact.value] = by_impact.get(r.impact.value, 0) + 1
        avg_rate = (
            round(
                sum(r.rollback_rate_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        high_count = sum(
            1 for r in self._records if r.impact in (RollbackImpact.CRITICAL, RollbackImpact.HIGH)
        )
        recs: list[str] = []
        if high_count > 0:
            recs.append(f"{high_count} high/critical impact rollback(s) detected")
        above_threshold = sum(1 for r in self._records if r.rollback_rate_pct > self._max_rate_pct)
        if above_threshold > 0:
            recs.append(
                f"{above_threshold} rollback(s) exceed {self._max_rate_pct}% rate threshold"
            )
        if not recs:
            recs.append("Rollback rates within acceptable limits")
        return RollbackAnalyzerReport(
            total_rollbacks=len(self._records),
            total_patterns=len(self._patterns),
            avg_rollback_rate_pct=avg_rate,
            by_reason=by_reason,
            by_impact=by_impact,
            high_rollback_count=high_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._patterns.clear()
        logger.info("rollback_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        reason_dist: dict[str, int] = {}
        for r in self._records:
            key = r.reason.value
            reason_dist[key] = reason_dist.get(key, 0) + 1
        return {
            "total_rollbacks": len(self._records),
            "total_patterns": len(self._patterns),
            "max_rate_pct": self._max_rate_pct,
            "reason_distribution": reason_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
