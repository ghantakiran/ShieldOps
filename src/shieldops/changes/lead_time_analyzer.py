"""Change Lead Time Analyzer — track commit-to-production lead time and deployment velocity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LeadTimePhase(StrEnum):
    CODING = "coding"
    REVIEW = "review"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class VelocityGrade(StrEnum):
    ELITE = "elite"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CRITICAL = "critical"


class LeadTimeTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class LeadTimeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    phase: LeadTimePhase = LeadTimePhase.CODING
    grade: VelocityGrade = VelocityGrade.MEDIUM
    lead_time_hours: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PhaseBreakdown(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phase_name: str = ""
    phase: LeadTimePhase = LeadTimePhase.CODING
    grade: VelocityGrade = VelocityGrade.MEDIUM
    avg_hours: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LeadTimeReport(BaseModel):
    total_records: int = 0
    total_breakdowns: int = 0
    avg_lead_time_hours: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    slow_service_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeLeadTimeAnalyzer:
    """Track commit-to-production lead time and deployment velocity."""

    def __init__(
        self,
        max_records: int = 200000,
        max_lead_time_hours: float = 72.0,
    ) -> None:
        self._max_records = max_records
        self._max_lead_time_hours = max_lead_time_hours
        self._records: list[LeadTimeRecord] = []
        self._breakdowns: list[PhaseBreakdown] = []
        logger.info(
            "lead_time_analyzer.initialized",
            max_records=max_records,
            max_lead_time_hours=max_lead_time_hours,
        )

    # -- record / get / list ---------------------------------------------

    def record_lead_time(
        self,
        service_name: str,
        phase: LeadTimePhase = LeadTimePhase.CODING,
        grade: VelocityGrade = VelocityGrade.MEDIUM,
        lead_time_hours: float = 0.0,
        details: str = "",
    ) -> LeadTimeRecord:
        record = LeadTimeRecord(
            service_name=service_name,
            phase=phase,
            grade=grade,
            lead_time_hours=lead_time_hours,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "lead_time_analyzer.recorded",
            record_id=record.id,
            service_name=service_name,
            phase=phase.value,
        )
        return record

    def get_lead_time(self, record_id: str) -> LeadTimeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_lead_times(
        self,
        service_name: str | None = None,
        phase: LeadTimePhase | None = None,
        limit: int = 50,
    ) -> list[LeadTimeRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if phase is not None:
            results = [r for r in results if r.phase == phase]
        return results[-limit:]

    def add_breakdown(
        self,
        phase_name: str,
        phase: LeadTimePhase = LeadTimePhase.CODING,
        grade: VelocityGrade = VelocityGrade.MEDIUM,
        avg_hours: float = 0.0,
        description: str = "",
    ) -> PhaseBreakdown:
        breakdown = PhaseBreakdown(
            phase_name=phase_name,
            phase=phase,
            grade=grade,
            avg_hours=avg_hours,
            description=description,
        )
        self._breakdowns.append(breakdown)
        if len(self._breakdowns) > self._max_records:
            self._breakdowns = self._breakdowns[-self._max_records :]
        logger.info(
            "lead_time_analyzer.breakdown_added",
            phase_name=phase_name,
            phase=phase.value,
        )
        return breakdown

    # -- domain operations -----------------------------------------------

    def analyze_service_lead_time(self, service_name: str) -> dict[str, Any]:
        """Analyze lead time for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {
                "service_name": service_name,
                "status": "no_data",
            }
        total_hours = sum(r.lead_time_hours for r in records)
        avg_hours = round(total_hours / len(records), 2)
        return {
            "service_name": service_name,
            "avg_lead_time_hours": avg_hours,
            "record_count": len(records),
            "meets_threshold": avg_hours <= self._max_lead_time_hours,
        }

    def identify_slow_services(self) -> list[dict[str, Any]]:
        """Find services with more than one LOW or CRITICAL grade record."""
        by_service: dict[str, list[VelocityGrade]] = {}
        for r in self._records:
            by_service.setdefault(r.service_name, []).append(r.grade)
        results: list[dict[str, Any]] = []
        for service, grades in by_service.items():
            slow_count = sum(1 for g in grades if g in (VelocityGrade.LOW, VelocityGrade.CRITICAL))
            if slow_count > 1:
                results.append(
                    {
                        "service_name": service,
                        "slow_count": slow_count,
                        "total_records": len(grades),
                    }
                )
        results.sort(key=lambda x: x["slow_count"], reverse=True)
        return results

    def rank_by_lead_time(self) -> list[dict[str, Any]]:
        """Rank services by average lead time hours (descending)."""
        by_service: dict[str, list[float]] = {}
        for r in self._records:
            by_service.setdefault(r.service_name, []).append(r.lead_time_hours)
        results: list[dict[str, Any]] = []
        for service, hours in by_service.items():
            avg_hours = round(sum(hours) / len(hours), 2)
            results.append(
                {
                    "service_name": service,
                    "avg_lead_time_hours": avg_hours,
                    "record_count": len(hours),
                }
            )
        results.sort(key=lambda x: x["avg_lead_time_hours"], reverse=True)
        return results

    def detect_lead_time_trends(self) -> list[dict[str, Any]]:
        """Detect lead time trends for services with more than 3 records."""
        by_service: dict[str, list[LeadTimeRecord]] = {}
        for r in self._records:
            by_service.setdefault(r.service_name, []).append(r)
        results: list[dict[str, Any]] = []
        for service, records in by_service.items():
            if len(records) <= 3:
                continue
            mid = len(records) // 2
            older_avg = sum(r.lead_time_hours for r in records[:mid]) / mid
            recent_avg = sum(r.lead_time_hours for r in records[mid:]) / (len(records) - mid)
            if older_avg == 0:
                trend = LeadTimeTrend.INSUFFICIENT_DATA
            else:
                change_pct = ((recent_avg - older_avg) / older_avg) * 100
                if change_pct < -20:
                    trend = LeadTimeTrend.IMPROVING
                elif change_pct > 20:
                    trend = LeadTimeTrend.DEGRADING
                elif abs(change_pct) <= 20:
                    trend = LeadTimeTrend.STABLE
                else:
                    trend = LeadTimeTrend.VOLATILE
            results.append(
                {
                    "service_name": service,
                    "trend": trend.value,
                    "older_avg_hours": round(older_avg, 2),
                    "recent_avg_hours": round(recent_avg, 2),
                    "record_count": len(records),
                }
            )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> LeadTimeReport:
        by_phase: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_phase[r.phase.value] = by_phase.get(r.phase.value, 0) + 1
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
        avg_hours = (
            round(
                sum(r.lead_time_hours for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        slow_count = sum(
            1 for r in self._records if r.grade in (VelocityGrade.LOW, VelocityGrade.CRITICAL)
        )
        recs: list[str] = []
        if slow_count > 0:
            recs.append(f"{slow_count} record(s) with LOW or CRITICAL velocity grade")
        if avg_hours > self._max_lead_time_hours and self._records:
            recs.append(
                f"Average lead time {avg_hours}h exceeds threshold {self._max_lead_time_hours}h"
            )
        if not recs:
            recs.append("Lead times are within acceptable bounds")
        return LeadTimeReport(
            total_records=len(self._records),
            total_breakdowns=len(self._breakdowns),
            avg_lead_time_hours=avg_hours,
            by_phase=by_phase,
            by_grade=by_grade,
            slow_service_count=slow_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._breakdowns.clear()
        logger.info("lead_time_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            key = r.phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_breakdowns": len(self._breakdowns),
            "max_lead_time_hours": self._max_lead_time_hours,
            "phase_distribution": phase_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
