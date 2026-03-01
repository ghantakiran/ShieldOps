"""Knowledge Gap Detector — detect knowledge gaps across teams and domains."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFORMATIONAL = "informational"


class GapDomain(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    SECURITY = "security"
    NETWORKING = "networking"
    DATABASE = "database"


class GapStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DOCUMENTED = "documented"
    VERIFIED = "verified"
    CLOSED = "closed"


# --- Models ---


class KnowledgeGapRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_id: str = ""
    gap_severity: GapSeverity = GapSeverity.MODERATE
    gap_domain: GapDomain = GapDomain.INFRASTRUCTURE
    gap_status: GapStatus = GapStatus.OPEN
    coverage_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class GapAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_id: str = ""
    gap_severity: GapSeverity = GapSeverity.MODERATE
    assessment_score: float = 0.0
    threshold: float = 80.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeGapReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    critical_gaps: int = 0
    avg_coverage_pct: float = 0.0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gap_areas: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeGapDetector:
    """Detect knowledge gaps across teams, identify undocumented areas."""

    def __init__(
        self,
        max_records: int = 200000,
        min_coverage_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_coverage_pct = min_coverage_pct
        self._records: list[KnowledgeGapRecord] = []
        self._assessments: list[GapAssessment] = []
        logger.info(
            "knowledge_gap_detector.initialized",
            max_records=max_records,
            min_coverage_pct=min_coverage_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_gap(
        self,
        gap_id: str,
        gap_severity: GapSeverity = GapSeverity.MODERATE,
        gap_domain: GapDomain = GapDomain.INFRASTRUCTURE,
        gap_status: GapStatus = GapStatus.OPEN,
        coverage_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> KnowledgeGapRecord:
        record = KnowledgeGapRecord(
            gap_id=gap_id,
            gap_severity=gap_severity,
            gap_domain=gap_domain,
            gap_status=gap_status,
            coverage_pct=coverage_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_gap_detector.gap_recorded",
            record_id=record.id,
            gap_id=gap_id,
            gap_severity=gap_severity.value,
            gap_domain=gap_domain.value,
        )
        return record

    def get_gap(self, record_id: str) -> KnowledgeGapRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_gaps(
        self,
        gap_severity: GapSeverity | None = None,
        gap_domain: GapDomain | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeGapRecord]:
        results = list(self._records)
        if gap_severity is not None:
            results = [r for r in results if r.gap_severity == gap_severity]
        if gap_domain is not None:
            results = [r for r in results if r.gap_domain == gap_domain]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        gap_id: str,
        gap_severity: GapSeverity = GapSeverity.MODERATE,
        assessment_score: float = 0.0,
        threshold: float = 80.0,
        description: str = "",
    ) -> GapAssessment:
        breached = assessment_score < threshold
        assessment = GapAssessment(
            gap_id=gap_id,
            gap_severity=gap_severity,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "knowledge_gap_detector.assessment_added",
            gap_id=gap_id,
            gap_severity=gap_severity.value,
            assessment_score=assessment_score,
            breached=breached,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_gap_distribution(self) -> dict[str, Any]:
        """Group by gap_severity; return count and avg coverage per severity."""
        severity_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.gap_severity.value
            severity_data.setdefault(key, []).append(r.coverage_pct)
        result: dict[str, Any] = {}
        for severity, scores in severity_data.items():
            result[severity] = {
                "count": len(scores),
                "avg_coverage_pct": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_critical_gaps(self) -> list[dict[str, Any]]:
        """Return gaps where severity is CRITICAL or HIGH."""
        critical_severities = {
            GapSeverity.CRITICAL,
            GapSeverity.HIGH,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.gap_severity in critical_severities:
                results.append(
                    {
                        "record_id": r.id,
                        "gap_id": r.gap_id,
                        "gap_severity": r.gap_severity.value,
                        "gap_domain": r.gap_domain.value,
                        "coverage_pct": r.coverage_pct,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["coverage_pct"], reverse=False)
        return results

    def rank_by_coverage(self) -> list[dict[str, Any]]:
        """Group by service, avg coverage_pct, sort asc — worst first."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service, []).append(r.coverage_pct)
        results: list[dict[str, Any]] = []
        for svc, scores in service_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_coverage_pct": round(sum(scores) / len(scores), 2),
                    "gap_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_pct"], reverse=False)
        return results

    def detect_gap_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.assessment_score for a in self._assessments]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> KnowledgeGapReport:
        by_severity: dict[str, int] = {}
        by_domain: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_severity[r.gap_severity.value] = by_severity.get(r.gap_severity.value, 0) + 1
            by_domain[r.gap_domain.value] = by_domain.get(r.gap_domain.value, 0) + 1
            by_status[r.gap_status.value] = by_status.get(r.gap_status.value, 0) + 1
        critical_gaps = sum(
            1 for r in self._records if r.gap_severity in {GapSeverity.CRITICAL, GapSeverity.HIGH}
        )
        avg_coverage = (
            round(
                sum(r.coverage_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        critical_list = self.identify_critical_gaps()
        top_gap_areas = [c["gap_id"] for c in critical_list]
        recs: list[str] = []
        if critical_gaps > 0:
            recs.append(f"{critical_gaps} critical/high gap(s) detected — prioritize documentation")
        low_cov = sum(1 for r in self._records if r.coverage_pct < self._min_coverage_pct)
        if low_cov > 0:
            recs.append(f"{low_cov} gap(s) below coverage threshold ({self._min_coverage_pct}%)")
        if not recs:
            recs.append("Knowledge coverage levels are acceptable")
        return KnowledgeGapReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            critical_gaps=critical_gaps,
            avg_coverage_pct=avg_coverage,
            by_severity=by_severity,
            by_domain=by_domain,
            by_status=by_status,
            top_gap_areas=top_gap_areas,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("knowledge_gap_detector.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        severity_dist: dict[str, int] = {}
        for r in self._records:
            key = r.gap_severity.value
            severity_dist[key] = severity_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "min_coverage_pct": self._min_coverage_pct,
            "severity_distribution": severity_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
