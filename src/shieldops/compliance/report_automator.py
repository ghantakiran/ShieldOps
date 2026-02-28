"""Compliance Report Automator — automate and track compliance report generation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ReportType(StrEnum):
    SOC2_AUDIT = "soc2_audit"
    HIPAA_ASSESSMENT = "hipaa_assessment"
    PCI_DSS_REVIEW = "pci_dss_review"
    ISO27001_AUDIT = "iso27001_audit"
    GDPR_COMPLIANCE = "gdpr_compliance"


class ReportStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ReportFrequency(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    ON_DEMAND = "on_demand"


# --- Models ---


class ReportRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    report_name: str = ""
    report_type: ReportType = ReportType.SOC2_AUDIT
    status: ReportStatus = ReportStatus.DRAFT
    completion_score: float = 0.0
    frequency: ReportFrequency = ReportFrequency.QUARTERLY
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ReportSection(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    section_name: str = ""
    report_type: ReportType = ReportType.SOC2_AUDIT
    status: ReportStatus = ReportStatus.DRAFT
    completion_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReportAutomatorReport(BaseModel):
    total_reports: int = 0
    total_sections: int = 0
    avg_completion_score_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    overdue_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceReportAutomator:
    """Automate compliance report generation, track overdue reports, and identify gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        max_overdue_days: float = 14.0,
    ) -> None:
        self._max_records = max_records
        self._max_overdue_days = max_overdue_days
        self._records: list[ReportRecord] = []
        self._sections: list[ReportSection] = []
        logger.info(
            "report_automator.initialized",
            max_records=max_records,
            max_overdue_days=max_overdue_days,
        )

    # -- record / get / list ---------------------------------------------

    def record_report(
        self,
        report_name: str,
        report_type: ReportType = ReportType.SOC2_AUDIT,
        status: ReportStatus = ReportStatus.DRAFT,
        completion_score: float = 0.0,
        frequency: ReportFrequency = ReportFrequency.QUARTERLY,
        details: str = "",
    ) -> ReportRecord:
        record = ReportRecord(
            report_name=report_name,
            report_type=report_type,
            status=status,
            completion_score=completion_score,
            frequency=frequency,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "report_automator.recorded",
            record_id=record.id,
            report_name=report_name,
            report_type=report_type.value,
            status=status.value,
        )
        return record

    def get_report(self, record_id: str) -> ReportRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_reports(
        self,
        report_type: ReportType | None = None,
        status: ReportStatus | None = None,
        limit: int = 50,
    ) -> list[ReportRecord]:
        results = list(self._records)
        if report_type is not None:
            results = [r for r in results if r.report_type == report_type]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    def add_section(
        self,
        section_name: str,
        report_type: ReportType = ReportType.SOC2_AUDIT,
        status: ReportStatus = ReportStatus.DRAFT,
        completion_score: float = 0.0,
        description: str = "",
    ) -> ReportSection:
        section = ReportSection(
            section_name=section_name,
            report_type=report_type,
            status=status,
            completion_score=completion_score,
            description=description,
        )
        self._sections.append(section)
        if len(self._sections) > self._max_records:
            self._sections = self._sections[-self._max_records :]
        logger.info(
            "report_automator.section_added",
            section_name=section_name,
            report_type=report_type.value,
            status=status.value,
        )
        return section

    # -- domain operations -----------------------------------------------

    def analyze_report_by_type(self, report_type: ReportType) -> dict[str, Any]:
        records = [r for r in self._records if r.report_type == report_type]
        if not records:
            return {"report_type": report_type.value, "status": "no_data"}
        avg_score = round(sum(r.completion_score for r in records) / len(records), 2)
        incomplete = sum(
            1 for r in records if r.status in (ReportStatus.DRAFT, ReportStatus.IN_REVIEW)
        )
        return {
            "report_type": report_type.value,
            "total_records": len(records),
            "avg_completion_score": avg_score,
            "incomplete_count": incomplete,
            "below_threshold": avg_score < (100.0 - self._max_overdue_days),
        }

    def identify_overdue_reports(self) -> list[dict[str, Any]]:
        overdue_counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (ReportStatus.DRAFT, ReportStatus.IN_REVIEW):
                overdue_counts[r.report_name] = overdue_counts.get(r.report_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, count in overdue_counts.items():
            if count > 1:
                results.append({"report_name": name, "overdue_count": count})
        results.sort(key=lambda x: x["overdue_count"], reverse=True)
        return results

    def rank_by_completion_score(self) -> list[dict[str, Any]]:
        type_scores: dict[str, list[float]] = {}
        for r in self._records:
            type_scores.setdefault(r.report_type.value, []).append(r.completion_score)
        results: list[dict[str, Any]] = []
        for rtype, scores in type_scores.items():
            results.append(
                {
                    "report_type": rtype,
                    "avg_completion_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_completion_score"], reverse=True)
        return results

    def detect_reporting_gaps(self) -> list[dict[str, Any]]:
        type_counts: dict[str, int] = {}
        for r in self._records:
            type_counts[r.report_type.value] = type_counts.get(r.report_type.value, 0) + 1
        results: list[dict[str, Any]] = []
        for rtype, count in type_counts.items():
            if count > 3:
                results.append(
                    {
                        "report_type": rtype,
                        "report_count": count,
                        "gap_detected": True,
                    }
                )
        results.sort(key=lambda x: x["report_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ReportAutomatorReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.report_type.value] = by_type.get(r.report_type.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        avg_score = (
            round(sum(r.completion_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        overdue = sum(
            1 for r in self._records if r.status in (ReportStatus.DRAFT, ReportStatus.IN_REVIEW)
        )
        recs: list[str] = []
        if overdue > 0:
            recs.append(f"{overdue} report(s) still in draft or in-review state")
        gaps = len(self.detect_reporting_gaps())
        if gaps > 0:
            recs.append(f"{gaps} report type(s) with recurring reporting gaps")
        if not recs:
            recs.append("All compliance reports are within acceptable completion thresholds")
        return ReportAutomatorReport(
            total_reports=len(self._records),
            total_sections=len(self._sections),
            avg_completion_score_pct=avg_score,
            by_type=by_type,
            by_status=by_status,
            overdue_count=overdue,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._sections.clear()
        logger.info("report_automator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.report_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_reports": len(self._records),
            "total_sections": len(self._sections),
            "max_overdue_days": self._max_overdue_days,
            "type_distribution": type_dist,
            "unique_report_names": len({r.report_name for r in self._records}),
        }
