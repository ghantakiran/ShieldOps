"""Audit Readiness Scorer — score and track audit readiness across areas."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReadinessArea(StrEnum):
    DOCUMENTATION = "documentation"
    EVIDENCE_COLLECTION = "evidence_collection"
    CONTROL_TESTING = "control_testing"
    ACCESS_REVIEW = "access_review"
    RISK_ASSESSMENT = "risk_assessment"


class ReadinessGrade(StrEnum):
    AUDIT_READY = "audit_ready"
    MOSTLY_READY = "mostly_ready"
    PARTIALLY_READY = "partially_ready"
    NOT_READY = "not_ready"
    CRITICAL_GAPS = "critical_gaps"


class ReadinessGap(StrEnum):
    MISSING_EVIDENCE = "missing_evidence"
    STALE_CONTROLS = "stale_controls"
    INCOMPLETE_DOCUMENTATION = "incomplete_documentation"
    UNTESTED_CONTROLS = "untested_controls"
    ACCESS_ISSUES = "access_issues"


# --- Models ---


class ReadinessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    area_name: str = ""
    area: ReadinessArea = ReadinessArea.DOCUMENTATION
    grade: ReadinessGrade = ReadinessGrade.PARTIALLY_READY
    gap: ReadinessGap = ReadinessGap.MISSING_EVIDENCE
    readiness_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ReadinessAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    area_name: str = ""
    area: ReadinessArea = ReadinessArea.DOCUMENTATION
    grade: ReadinessGrade = ReadinessGrade.PARTIALLY_READY
    min_readiness_pct: float = 80.0
    review_frequency_days: float = 30.0
    created_at: float = Field(default_factory=time.time)


class AuditReadinessReport(BaseModel):
    total_records: int = 0
    total_assessments: int = 0
    ready_rate_pct: float = 0.0
    by_area: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    critical_gap_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditReadinessScorer:
    """Score and track audit readiness across areas."""

    def __init__(
        self,
        max_records: int = 200000,
        min_readiness_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_readiness_pct = min_readiness_pct
        self._records: list[ReadinessRecord] = []
        self._assessments: list[ReadinessAssessment] = []
        logger.info(
            "audit_readiness.initialized",
            max_records=max_records,
            min_readiness_pct=min_readiness_pct,
        )

    # -- record / get / list -------------------------------------------

    def record_readiness(
        self,
        area_name: str,
        area: ReadinessArea = ReadinessArea.DOCUMENTATION,
        grade: ReadinessGrade = ReadinessGrade.PARTIALLY_READY,
        gap: ReadinessGap = ReadinessGap.MISSING_EVIDENCE,
        readiness_pct: float = 0.0,
        details: str = "",
    ) -> ReadinessRecord:
        record = ReadinessRecord(
            area_name=area_name,
            area=area,
            grade=grade,
            gap=gap,
            readiness_pct=readiness_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_readiness.readiness_recorded",
            record_id=record.id,
            area_name=area_name,
            area=area.value,
            grade=grade.value,
        )
        return record

    def get_readiness(self, record_id: str) -> ReadinessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_readiness_records(
        self,
        area_name: str | None = None,
        area: ReadinessArea | None = None,
        limit: int = 50,
    ) -> list[ReadinessRecord]:
        results = list(self._records)
        if area_name is not None:
            results = [r for r in results if r.area_name == area_name]
        if area is not None:
            results = [r for r in results if r.area == area]
        return results[-limit:]

    def add_assessment(
        self,
        area_name: str,
        area: ReadinessArea = ReadinessArea.DOCUMENTATION,
        grade: ReadinessGrade = ReadinessGrade.PARTIALLY_READY,
        min_readiness_pct: float = 80.0,
        review_frequency_days: float = 30.0,
    ) -> ReadinessAssessment:
        assessment = ReadinessAssessment(
            area_name=area_name,
            area=area,
            grade=grade,
            min_readiness_pct=min_readiness_pct,
            review_frequency_days=review_frequency_days,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "audit_readiness.assessment_added",
            area_name=area_name,
            area=area.value,
            grade=grade.value,
        )
        return assessment

    # -- domain operations --------------------------------------------

    def analyze_readiness_by_area(self, area_name: str) -> dict[str, Any]:
        """Analyze readiness for a specific area."""
        records = [r for r in self._records if r.area_name == area_name]
        if not records:
            return {"area_name": area_name, "status": "no_data"}
        ready_count = sum(
            1
            for r in records
            if r.grade in (ReadinessGrade.AUDIT_READY, ReadinessGrade.MOSTLY_READY)
        )
        ready_rate = round(ready_count / len(records) * 100, 2)
        avg_readiness = round(sum(r.readiness_pct for r in records) / len(records), 2)
        return {
            "area_name": area_name,
            "record_count": len(records),
            "ready_count": ready_count,
            "ready_rate_pct": ready_rate,
            "avg_readiness_pct": avg_readiness,
            "meets_threshold": avg_readiness >= self._min_readiness_pct,
        }

    def identify_critical_gaps(self) -> list[dict[str, Any]]:
        """Find areas with repeated critical gaps."""
        gap_counts: dict[str, int] = {}
        for r in self._records:
            if r.grade in (ReadinessGrade.NOT_READY, ReadinessGrade.CRITICAL_GAPS):
                gap_counts[r.area_name] = gap_counts.get(r.area_name, 0) + 1
        results: list[dict[str, Any]] = []
        for area, count in gap_counts.items():
            if count > 1:
                results.append(
                    {
                        "area_name": area,
                        "critical_gap_count": count,
                    }
                )
        results.sort(key=lambda x: x["critical_gap_count"], reverse=True)
        return results

    def rank_by_readiness_score(self) -> list[dict[str, Any]]:
        """Rank areas by avg readiness score descending."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self._records:
            totals[r.area_name] = totals.get(r.area_name, 0.0) + r.readiness_pct
            counts[r.area_name] = counts.get(r.area_name, 0) + 1
        results: list[dict[str, Any]] = []
        for area in totals:
            avg = round(totals[area] / counts[area], 2)
            results.append(
                {
                    "area_name": area,
                    "avg_readiness_pct": avg,
                }
            )
        results.sort(key=lambda x: x["avg_readiness_pct"], reverse=True)
        return results

    def detect_readiness_trends(self) -> list[dict[str, Any]]:
        """Detect areas with >3 non-ready records."""
        not_ready_counts: dict[str, int] = {}
        for r in self._records:
            if r.grade not in (ReadinessGrade.AUDIT_READY, ReadinessGrade.MOSTLY_READY):
                not_ready_counts[r.area_name] = not_ready_counts.get(r.area_name, 0) + 1
        results: list[dict[str, Any]] = []
        for area, count in not_ready_counts.items():
            if count > 3:
                results.append(
                    {
                        "area_name": area,
                        "not_ready_count": count,
                        "trend_detected": True,
                    }
                )
        results.sort(key=lambda x: x["not_ready_count"], reverse=True)
        return results

    # -- report / stats -----------------------------------------------

    def generate_report(self) -> AuditReadinessReport:
        by_area: dict[str, int] = {}
        by_grade: dict[str, int] = {}
        for r in self._records:
            by_area[r.area.value] = by_area.get(r.area.value, 0) + 1
            by_grade[r.grade.value] = by_grade.get(r.grade.value, 0) + 1
        ready_count = sum(
            1
            for r in self._records
            if r.grade in (ReadinessGrade.AUDIT_READY, ReadinessGrade.MOSTLY_READY)
        )
        ready_rate = round(ready_count / len(self._records) * 100, 2) if self._records else 0.0
        critical_gaps = sum(1 for _ in self.identify_critical_gaps())
        recs: list[str] = []
        if self._records and ready_rate < self._min_readiness_pct:
            recs.append(f"Ready rate {ready_rate}% is below {self._min_readiness_pct}% threshold")
        if critical_gaps > 0:
            recs.append(f"{critical_gaps} area(s) with critical gaps")
        trends = len(self.detect_readiness_trends())
        if trends > 0:
            recs.append(f"{trends} area(s) detected with readiness trends")
        if not recs:
            recs.append("Audit readiness is healthy and on track")
        return AuditReadinessReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            ready_rate_pct=ready_rate,
            by_area=by_area,
            by_grade=by_grade,
            critical_gap_count=critical_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("audit_readiness.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        area_dist: dict[str, int] = {}
        for r in self._records:
            key = r.area.value
            area_dist[key] = area_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "min_readiness_pct": self._min_readiness_pct,
            "area_distribution": area_dist,
            "unique_areas": len({r.area_name for r in self._records}),
        }
