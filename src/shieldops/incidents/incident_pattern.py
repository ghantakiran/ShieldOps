"""Incident Pattern Detector — detect recurring incident patterns and anti-patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PatternType(StrEnum):
    RECURRING_FAILURE = "recurring_failure"
    CASCADING_IMPACT = "cascading_impact"
    TIME_BASED = "time_based"
    DEPLOYMENT_RELATED = "deployment_related"
    CONFIGURATION_DRIFT = "configuration_drift"


class PatternSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFORMATIONAL = "informational"


class PatternFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    RARE = "rare"


# --- Models ---


class PatternRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    pattern_type: PatternType = PatternType.RECURRING_FAILURE
    pattern_severity: PatternSeverity = PatternSeverity.INFORMATIONAL
    pattern_frequency: PatternFrequency = PatternFrequency.RARE
    confidence_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PatternOccurrence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    pattern_type: PatternType = PatternType.RECURRING_FAILURE
    occurrence_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentPatternReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_occurrences: int = 0
    critical_patterns: int = 0
    avg_confidence_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    top_patterns: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentPatternDetector:
    """Detect recurring incident patterns, anti-patterns, and improvement recommendations."""

    def __init__(
        self,
        max_records: int = 200000,
        max_critical_pattern_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_critical_pattern_pct = max_critical_pattern_pct
        self._records: list[PatternRecord] = []
        self._occurrences: list[PatternOccurrence] = []
        logger.info(
            "incident_pattern.initialized",
            max_records=max_records,
            max_critical_pattern_pct=max_critical_pattern_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_pattern(
        self,
        pattern_id: str,
        pattern_type: PatternType = PatternType.RECURRING_FAILURE,
        pattern_severity: PatternSeverity = PatternSeverity.INFORMATIONAL,
        pattern_frequency: PatternFrequency = PatternFrequency.RARE,
        confidence_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PatternRecord:
        record = PatternRecord(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            pattern_severity=pattern_severity,
            pattern_frequency=pattern_frequency,
            confidence_score=confidence_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_pattern.pattern_recorded",
            record_id=record.id,
            pattern_id=pattern_id,
            pattern_type=pattern_type.value,
            pattern_severity=pattern_severity.value,
        )
        return record

    def get_pattern(self, record_id: str) -> PatternRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_patterns(
        self,
        pattern_type: PatternType | None = None,
        severity: PatternSeverity | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PatternRecord]:
        results = list(self._records)
        if pattern_type is not None:
            results = [r for r in results if r.pattern_type == pattern_type]
        if severity is not None:
            results = [r for r in results if r.pattern_severity == severity]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_occurrence(
        self,
        pattern_id: str,
        pattern_type: PatternType = PatternType.RECURRING_FAILURE,
        occurrence_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PatternOccurrence:
        occurrence = PatternOccurrence(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            occurrence_score=occurrence_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._occurrences.append(occurrence)
        if len(self._occurrences) > self._max_records:
            self._occurrences = self._occurrences[-self._max_records :]
        logger.info(
            "incident_pattern.occurrence_added",
            pattern_id=pattern_id,
            pattern_type=pattern_type.value,
            occurrence_score=occurrence_score,
        )
        return occurrence

    # -- domain operations --------------------------------------------------

    def analyze_pattern_distribution(self) -> dict[str, Any]:
        """Group by pattern type; return count and avg confidence per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.pattern_type.value
            type_data.setdefault(key, []).append(r.confidence_score)
        result: dict[str, Any] = {}
        for ptype, scores in type_data.items():
            result[ptype] = {
                "count": len(scores),
                "avg_confidence": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_critical_patterns(self) -> list[dict[str, Any]]:
        """Return records where severity is CRITICAL."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.pattern_severity == PatternSeverity.CRITICAL:
                results.append(
                    {
                        "record_id": r.id,
                        "pattern_id": r.pattern_id,
                        "pattern_type": r.pattern_type.value,
                        "confidence_score": r.confidence_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_confidence(self) -> list[dict[str, Any]]:
        """Group by service, avg confidence score, sort descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.confidence_score)
        results: list[dict[str, Any]] = []
        for service, scores in svc_scores.items():
            results.append(
                {
                    "service": service,
                    "avg_confidence": round(sum(scores) / len(scores), 2),
                    "pattern_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_confidence"], reverse=True)
        return results

    def detect_pattern_trends(self) -> dict[str, Any]:
        """Split-half comparison on occurrence_score; delta threshold 5.0."""
        if len(self._occurrences) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [o.occurrence_score for o in self._occurrences]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> IncidentPatternReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_frequency: dict[str, int] = {}
        for r in self._records:
            by_type[r.pattern_type.value] = by_type.get(r.pattern_type.value, 0) + 1
            by_severity[r.pattern_severity.value] = by_severity.get(r.pattern_severity.value, 0) + 1
            by_frequency[r.pattern_frequency.value] = (
                by_frequency.get(r.pattern_frequency.value, 0) + 1
            )
        critical_patterns = sum(
            1 for r in self._records if r.pattern_severity == PatternSeverity.CRITICAL
        )
        avg_confidence = (
            round(sum(r.confidence_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_confidence()
        top_patterns = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if critical_patterns > 0:
            recs.append(
                f"{critical_patterns} critical pattern(s) detected — review incident sources"
            )
        critical_pct = (
            round(critical_patterns / len(self._records) * 100, 2) if self._records else 0.0
        )
        if critical_pct > self._max_critical_pattern_pct:
            recs.append(
                f"Critical pattern rate {critical_pct}% exceeds "
                f"threshold ({self._max_critical_pattern_pct}%)"
            )
        if not recs:
            recs.append("Incident pattern levels are healthy")
        return IncidentPatternReport(
            total_records=len(self._records),
            total_occurrences=len(self._occurrences),
            critical_patterns=critical_patterns,
            avg_confidence_score=avg_confidence,
            by_type=by_type,
            by_severity=by_severity,
            by_frequency=by_frequency,
            top_patterns=top_patterns,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._occurrences.clear()
        logger.info("incident_pattern.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.pattern_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_occurrences": len(self._occurrences),
            "max_critical_pattern_pct": self._max_critical_pattern_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
