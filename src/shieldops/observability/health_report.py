"""Service Health Report Card — generates periodic health reports."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HealthGrade(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class ReportStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class HealthMetric(BaseModel):
    name: str
    value: float = 0.0
    weight: float = 1.0
    grade: HealthGrade = HealthGrade.C


class HealthReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str
    metrics: list[HealthMetric] = Field(default_factory=list)
    overall_grade: HealthGrade = HealthGrade.C
    overall_score: float = 0.0
    status: ReportStatus = ReportStatus.DRAFT
    recommendations: list[str] = Field(default_factory=list)
    period_start: float = 0.0
    period_end: float = 0.0
    created_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def _grade_from_value(value: float) -> HealthGrade:
    """Map a numeric value (0-100 scale) to a health grade."""
    if value >= 90:
        return HealthGrade.A
    if value >= 80:
        return HealthGrade.B
    if value >= 70:
        return HealthGrade.C
    if value >= 60:
        return HealthGrade.D
    return HealthGrade.F


class ServiceHealthReportGenerator:
    """Generates periodic health report cards for services."""

    def __init__(self, max_reports: int = 10000) -> None:
        self.max_reports = max_reports
        self._reports: dict[str, HealthReport] = {}
        logger.info(
            "health_report_generator.initialized",
            max_reports=max_reports,
        )

    def create_report(
        self,
        service: str,
        period_start: float,
        period_end: float,
    ) -> HealthReport:
        """Create a new draft health report for a service."""
        if len(self._reports) >= self.max_reports:
            oldest_key = next(iter(self._reports))
            del self._reports[oldest_key]
        report = HealthReport(
            service=service,
            period_start=period_start,
            period_end=period_end,
        )
        self._reports[report.id] = report
        logger.info(
            "health_report_generator.report_created",
            report_id=report.id,
            service=service,
        )
        return report

    def add_metric(
        self,
        report_id: str,
        name: str,
        value: float,
        weight: float = 1.0,
    ) -> HealthReport | None:
        """Add a health metric to a report with auto-grading."""
        report = self._reports.get(report_id)
        if report is None:
            return None
        grade = _grade_from_value(value)
        metric = HealthMetric(
            name=name,
            value=value,
            weight=weight,
            grade=grade,
        )
        report.metrics.append(metric)
        logger.info(
            "health_report_generator.metric_added",
            report_id=report_id,
            metric_name=name,
            value=value,
            grade=grade,
        )
        return report

    def add_recommendation(
        self,
        report_id: str,
        recommendation: str,
    ) -> HealthReport | None:
        """Add a recommendation to a health report."""
        report = self._reports.get(report_id)
        if report is None:
            return None
        report.recommendations.append(recommendation)
        logger.info(
            "health_report_generator.recommendation_added",
            report_id=report_id,
        )
        return report

    def publish_report(self, report_id: str) -> HealthReport | None:
        """Transition a report from draft to published."""
        report = self._reports.get(report_id)
        if report is None:
            return None
        report.status = ReportStatus.PUBLISHED
        logger.info(
            "health_report_generator.report_published",
            report_id=report_id,
            service=report.service,
        )
        return report

    def archive_report(self, report_id: str) -> HealthReport | None:
        """Archive a report."""
        report = self._reports.get(report_id)
        if report is None:
            return None
        report.status = ReportStatus.ARCHIVED
        logger.info(
            "health_report_generator.report_archived",
            report_id=report_id,
        )
        return report

    def calculate_overall(self, report_id: str) -> HealthReport | None:
        """Compute weighted average of metrics and set overall grade."""
        report = self._reports.get(report_id)
        if report is None:
            return None
        if not report.metrics:
            report.overall_score = 0.0
            report.overall_grade = HealthGrade.F
            return report
        total_weight = sum(m.weight for m in report.metrics)
        if total_weight == 0:
            report.overall_score = 0.0
            report.overall_grade = HealthGrade.F
            return report
        weighted_sum = sum(m.value * m.weight for m in report.metrics)
        score = round(weighted_sum / total_weight, 2)
        report.overall_score = score
        report.overall_grade = _grade_from_value(score)
        logger.info(
            "health_report_generator.overall_calculated",
            report_id=report_id,
            overall_score=score,
            overall_grade=report.overall_grade,
        )
        return report

    def get_report(self, report_id: str) -> HealthReport | None:
        """Return a report by ID."""
        return self._reports.get(report_id)

    def list_reports(
        self,
        service: str | None = None,
        status: ReportStatus | str | None = None,
    ) -> list[HealthReport]:
        """List reports with optional filters."""
        results = list(self._reports.values())
        if service is not None:
            results = [r for r in results if r.service == service]
        if status is not None:
            s = ReportStatus(status) if isinstance(status, str) else status
            results = [r for r in results if r.status == s]
        return results

    def get_latest_report(self, service: str) -> HealthReport | None:
        """Return the most recent report for a service."""
        candidates = [r for r in self._reports.values() if r.service == service]
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.created_at)

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        reports = list(self._reports.values())
        status_dist: dict[str, int] = {}
        grade_dist: dict[str, int] = {}
        services: set[str] = set()
        for r in reports:
            status_dist[r.status] = status_dist.get(r.status, 0) + 1
            grade_dist[r.overall_grade] = grade_dist.get(r.overall_grade, 0) + 1
            services.add(r.service)
        return {
            "total_reports": len(reports),
            "services_covered": len(services),
            "status_distribution": status_dist,
            "grade_distribution": grade_dist,
        }
