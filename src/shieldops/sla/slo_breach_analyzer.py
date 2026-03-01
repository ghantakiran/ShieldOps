"""SLO Breach Analyzer — analyze SLO breaches, root causes, and impact."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BreachType(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    DURABILITY = "durability"


class BreachSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    COSMETIC = "cosmetic"


class BreachCause(StrEnum):
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    CODE_BUG = "code_bug"
    DEPENDENCY_ISSUE = "dependency_issue"
    CAPACITY_LIMIT = "capacity_limit"
    EXTERNAL_FACTOR = "external_factor"


# --- Models ---


class BreachRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    breach_id: str = ""
    breach_type: BreachType = BreachType.AVAILABILITY
    breach_severity: BreachSeverity = BreachSeverity.MODERATE
    breach_cause: BreachCause = BreachCause.INFRASTRUCTURE_FAILURE
    breach_duration_minutes: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BreachImpactAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    breach_id: str = ""
    breach_type: BreachType = BreachType.AVAILABILITY
    impact_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SLOBreachReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    critical_breaches: int = 0
    avg_breach_duration_minutes: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_cause: dict[str, int] = Field(default_factory=dict)
    top_breaching_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOBreachAnalyzer:
    """Analyze SLO breaches, root causes, and impact assessment."""

    def __init__(
        self,
        max_records: int = 200000,
        max_breach_duration_minutes: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._max_breach_duration_minutes = max_breach_duration_minutes
        self._records: list[BreachRecord] = []
        self._assessments: list[BreachImpactAssessment] = []
        logger.info(
            "slo_breach_analyzer.initialized",
            max_records=max_records,
            max_breach_duration_minutes=max_breach_duration_minutes,
        )

    # -- record / get / list ------------------------------------------------

    def record_breach(
        self,
        breach_id: str,
        breach_type: BreachType = BreachType.AVAILABILITY,
        breach_severity: BreachSeverity = BreachSeverity.MODERATE,
        breach_cause: BreachCause = BreachCause.INFRASTRUCTURE_FAILURE,
        breach_duration_minutes: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BreachRecord:
        record = BreachRecord(
            breach_id=breach_id,
            breach_type=breach_type,
            breach_severity=breach_severity,
            breach_cause=breach_cause,
            breach_duration_minutes=breach_duration_minutes,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_breach_analyzer.breach_recorded",
            record_id=record.id,
            breach_id=breach_id,
            breach_type=breach_type.value,
            breach_severity=breach_severity.value,
        )
        return record

    def get_breach(self, record_id: str) -> BreachRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_breaches(
        self,
        breach_type: BreachType | None = None,
        breach_severity: BreachSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[BreachRecord]:
        results = list(self._records)
        if breach_type is not None:
            results = [r for r in results if r.breach_type == breach_type]
        if breach_severity is not None:
            results = [r for r in results if r.breach_severity == breach_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        breach_id: str,
        breach_type: BreachType = BreachType.AVAILABILITY,
        impact_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BreachImpactAssessment:
        assessment = BreachImpactAssessment(
            breach_id=breach_id,
            breach_type=breach_type,
            impact_score=impact_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "slo_breach_analyzer.assessment_added",
            breach_id=breach_id,
            breach_type=breach_type.value,
            impact_score=impact_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_breach_distribution(self) -> dict[str, Any]:
        """Group by breach_type; return count and avg duration."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.breach_type.value
            type_data.setdefault(key, []).append(r.breach_duration_minutes)
        result: dict[str, Any] = {}
        for btype, durations in type_data.items():
            result[btype] = {
                "count": len(durations),
                "avg_duration": round(sum(durations) / len(durations), 2),
            }
        return result

    def identify_critical_breaches(self) -> list[dict[str, Any]]:
        """Return breaches where severity is CRITICAL or MAJOR."""
        critical_severities = {
            BreachSeverity.CRITICAL,
            BreachSeverity.MAJOR,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.breach_severity in critical_severities:
                results.append(
                    {
                        "record_id": r.id,
                        "breach_id": r.breach_id,
                        "breach_severity": r.breach_severity.value,
                        "breach_type": r.breach_type.value,
                        "breach_cause": r.breach_cause.value,
                        "breach_duration_minutes": r.breach_duration_minutes,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["breach_duration_minutes"], reverse=True)
        return results

    def rank_by_breach_duration(self) -> list[dict[str, Any]]:
        """Group by service, avg breach_duration_minutes, sort desc."""
        svc_durations: dict[str, list[float]] = {}
        for r in self._records:
            svc_durations.setdefault(r.service, []).append(r.breach_duration_minutes)
        results: list[dict[str, Any]] = []
        for svc, durations in svc_durations.items():
            results.append(
                {
                    "service": svc,
                    "avg_duration": round(sum(durations) / len(durations), 2),
                    "breach_count": len(durations),
                }
            )
        results.sort(key=lambda x: x["avg_duration"], reverse=True)
        return results

    def detect_breach_trends(self) -> dict[str, Any]:
        """Split-half comparison on impact_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.impact_score for a in self._assessments]
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

    def generate_report(self) -> SLOBreachReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_cause: dict[str, int] = {}
        for r in self._records:
            by_type[r.breach_type.value] = by_type.get(r.breach_type.value, 0) + 1
            by_severity[r.breach_severity.value] = by_severity.get(r.breach_severity.value, 0) + 1
            by_cause[r.breach_cause.value] = by_cause.get(r.breach_cause.value, 0) + 1
        critical_breaches = sum(
            1
            for r in self._records
            if r.breach_severity in {BreachSeverity.CRITICAL, BreachSeverity.MAJOR}
        )
        avg_duration = (
            round(
                sum(r.breach_duration_minutes for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        critical = self.identify_critical_breaches()
        top_breaching_services = [c["service"] for c in critical]
        recs: list[str] = []
        if critical:
            recs.append(f"{len(critical)} critical/major breach(es) detected — review SLO targets")
        long_breaches = sum(
            1
            for r in self._records
            if r.breach_duration_minutes > self._max_breach_duration_minutes
        )
        if long_breaches > 0:
            recs.append(
                f"{long_breaches} breach(es) exceeded duration threshold"
                f" ({self._max_breach_duration_minutes} min)"
            )
        if not recs:
            recs.append("SLO breach levels are acceptable")
        return SLOBreachReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            critical_breaches=critical_breaches,
            avg_breach_duration_minutes=avg_duration,
            by_type=by_type,
            by_severity=by_severity,
            by_cause=by_cause,
            top_breaching_services=top_breaching_services,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("slo_breach_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.breach_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "max_breach_duration_minutes": self._max_breach_duration_minutes,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
