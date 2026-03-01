"""Security Posture Gap Analyzer — identify gaps in security posture across services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GapCategory(StrEnum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    ENCRYPTION = "encryption"
    LOGGING = "logging"
    NETWORK = "network"


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFORMATIONAL = "informational"


class RemediationStatus(StrEnum):
    OPEN = "open"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"


# --- Models ---


class PostureGapRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_id: str = ""
    gap_category: GapCategory = GapCategory.AUTHENTICATION
    gap_severity: GapSeverity = GapSeverity.INFORMATIONAL
    remediation_status: RemediationStatus = RemediationStatus.OPEN
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class GapAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_id: str = ""
    gap_category: GapCategory = GapCategory.AUTHENTICATION
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SecurityPostureGapReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    critical_gaps: int = 0
    avg_risk_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_remediation: dict[str, int] = Field(default_factory=dict)
    top_critical: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityPostureGapAnalyzer:
    """Identify gaps in security posture across services."""

    def __init__(
        self,
        max_records: int = 200000,
        max_critical_gap_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_critical_gap_pct = max_critical_gap_pct
        self._records: list[PostureGapRecord] = []
        self._metrics: list[GapAssessment] = []
        logger.info(
            "security_posture_gap.initialized",
            max_records=max_records,
            max_critical_gap_pct=max_critical_gap_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_gap(
        self,
        gap_id: str,
        gap_category: GapCategory = GapCategory.AUTHENTICATION,
        gap_severity: GapSeverity = GapSeverity.INFORMATIONAL,
        remediation_status: RemediationStatus = RemediationStatus.OPEN,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PostureGapRecord:
        record = PostureGapRecord(
            gap_id=gap_id,
            gap_category=gap_category,
            gap_severity=gap_severity,
            remediation_status=remediation_status,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_posture_gap.gap_recorded",
            record_id=record.id,
            gap_id=gap_id,
            gap_category=gap_category.value,
            gap_severity=gap_severity.value,
        )
        return record

    def get_gap(self, record_id: str) -> PostureGapRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_gaps(
        self,
        category: GapCategory | None = None,
        severity: GapSeverity | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PostureGapRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.gap_category == category]
        if severity is not None:
            results = [r for r in results if r.gap_severity == severity]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        gap_id: str,
        gap_category: GapCategory = GapCategory.AUTHENTICATION,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> GapAssessment:
        metric = GapAssessment(
            gap_id=gap_id,
            gap_category=gap_category,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "security_posture_gap.assessment_added",
            gap_id=gap_id,
            gap_category=gap_category.value,
            assessment_score=assessment_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_gap_distribution(self) -> dict[str, Any]:
        """Group by gap_category; return count and avg risk_score."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.gap_category.value
            cat_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_critical_gaps(self) -> list[dict[str, Any]]:
        """Return records where gap_severity == CRITICAL."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.gap_severity == GapSeverity.CRITICAL:
                results.append(
                    {
                        "record_id": r.id,
                        "gap_id": r.gap_id,
                        "gap_category": r.gap_category.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_gap_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [m.assessment_score for m in self._metrics]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> SecurityPostureGapReport:
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_remediation: dict[str, int] = {}
        for r in self._records:
            by_category[r.gap_category.value] = by_category.get(r.gap_category.value, 0) + 1
            by_severity[r.gap_severity.value] = by_severity.get(r.gap_severity.value, 0) + 1
            by_remediation[r.remediation_status.value] = (
                by_remediation.get(r.remediation_status.value, 0) + 1
            )
        critical_gaps = sum(1 for r in self._records if r.gap_severity == GapSeverity.CRITICAL)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        rankings = self.rank_by_risk_score()
        top_critical = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if critical_gaps > 0:
            recs.append(
                f"{critical_gaps} critical gap(s) detected"
                f" (max acceptable {self._max_critical_gap_pct}%)"
            )
        high_gaps = sum(1 for r in self._records if r.gap_severity == GapSeverity.HIGH)
        if high_gaps > 0:
            recs.append(f"{high_gaps} high-severity gap(s) — prioritize remediation")
        if not recs:
            recs.append("Security posture gap levels are acceptable")
        return SecurityPostureGapReport(
            total_records=len(self._records),
            total_assessments=len(self._metrics),
            critical_gaps=critical_gaps,
            avg_risk_score=avg_risk_score,
            by_category=by_category,
            by_severity=by_severity,
            by_remediation=by_remediation,
            top_critical=top_critical,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("security_posture_gap.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.gap_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "max_critical_gap_pct": self._max_critical_gap_pct,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
