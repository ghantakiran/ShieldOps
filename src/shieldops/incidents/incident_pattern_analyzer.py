"""Incident Pattern Analyzer — analyze incident patterns across services."""

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
    RECURRING = "recurring"
    SEASONAL = "seasonal"
    CASCADING = "cascading"
    CORRELATED = "correlated"
    ISOLATED = "isolated"


class PatternConfidence(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SPECULATIVE = "speculative"


class PatternScope(StrEnum):
    SINGLE_SERVICE = "single_service"
    MULTI_SERVICE = "multi_service"
    PLATFORM_WIDE = "platform_wide"
    INFRASTRUCTURE = "infrastructure"
    EXTERNAL = "external"


# --- Models ---


class PatternRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    pattern_type: PatternType = PatternType.ISOLATED
    pattern_confidence: PatternConfidence = PatternConfidence.SPECULATIVE
    pattern_scope: PatternScope = PatternScope.SINGLE_SERVICE
    frequency_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PatternAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    pattern_type: PatternType = PatternType.ISOLATED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentPatternReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    recurring_patterns: int = 0
    avg_frequency_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    top_recurring: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentPatternAnalyzer:
    """Analyze incident patterns across services, identify recurring failure modes."""

    def __init__(
        self,
        max_records: int = 200000,
        max_recurring_pct: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._max_recurring_pct = max_recurring_pct
        self._records: list[PatternRecord] = []
        self._analyses: list[PatternAnalysis] = []
        logger.info(
            "incident_pattern_analyzer.initialized",
            max_records=max_records,
            max_recurring_pct=max_recurring_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_pattern(
        self,
        pattern_id: str,
        pattern_type: PatternType = PatternType.ISOLATED,
        pattern_confidence: PatternConfidence = PatternConfidence.SPECULATIVE,
        pattern_scope: PatternScope = PatternScope.SINGLE_SERVICE,
        frequency_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PatternRecord:
        record = PatternRecord(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            pattern_confidence=pattern_confidence,
            pattern_scope=pattern_scope,
            frequency_score=frequency_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_pattern_analyzer.pattern_recorded",
            record_id=record.id,
            pattern_id=pattern_id,
            pattern_type=pattern_type.value,
            pattern_confidence=pattern_confidence.value,
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
        pattern_confidence: PatternConfidence | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PatternRecord]:
        results = list(self._records)
        if pattern_type is not None:
            results = [r for r in results if r.pattern_type == pattern_type]
        if pattern_confidence is not None:
            results = [r for r in results if r.pattern_confidence == pattern_confidence]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        pattern_id: str,
        pattern_type: PatternType = PatternType.ISOLATED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PatternAnalysis:
        analysis = PatternAnalysis(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "incident_pattern_analyzer.analysis_added",
            pattern_id=pattern_id,
            pattern_type=pattern_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_pattern_distribution(self) -> dict[str, Any]:
        """Group by pattern_type; return count and avg frequency_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.pattern_type.value
            type_data.setdefault(key, []).append(r.frequency_score)
        result: dict[str, Any] = {}
        for ptype, scores in type_data.items():
            result[ptype] = {
                "count": len(scores),
                "avg_frequency_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_recurring_patterns(self) -> list[dict[str, Any]]:
        """Return records where pattern_type is RECURRING or CASCADING."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.pattern_type in (PatternType.RECURRING, PatternType.CASCADING):
                results.append(
                    {
                        "record_id": r.id,
                        "pattern_id": r.pattern_id,
                        "pattern_type": r.pattern_type.value,
                        "frequency_score": r.frequency_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_frequency(self) -> list[dict[str, Any]]:
        """Group by service, avg frequency_score, sort descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.frequency_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_frequency_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_frequency_score"], reverse=True)
        return results

    def detect_pattern_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "growing"
        else:
            trend = "shrinking"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> IncidentPatternReport:
        by_type: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_type[r.pattern_type.value] = by_type.get(r.pattern_type.value, 0) + 1
            by_confidence[r.pattern_confidence.value] = (
                by_confidence.get(r.pattern_confidence.value, 0) + 1
            )
            by_scope[r.pattern_scope.value] = by_scope.get(r.pattern_scope.value, 0) + 1
        recurring_patterns = sum(
            1
            for r in self._records
            if r.pattern_type in (PatternType.RECURRING, PatternType.CASCADING)
        )
        scores = [r.frequency_score for r in self._records]
        avg_frequency_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        recurring_list = self.identify_recurring_patterns()
        top_recurring = [o["pattern_id"] for o in recurring_list[:5]]
        recs: list[str] = []
        if self._records and recurring_patterns > 0:
            pct = round(recurring_patterns / len(self._records) * 100, 2)
            if pct > self._max_recurring_pct:
                recs.append(
                    f"Recurring pattern rate {pct}% exceeds threshold ({self._max_recurring_pct}%)"
                )
        if recurring_patterns > 0:
            recs.append(f"{recurring_patterns} recurring pattern(s) — investigate root causes")
        if not recs:
            recs.append("Incident pattern levels are healthy")
        return IncidentPatternReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            recurring_patterns=recurring_patterns,
            avg_frequency_score=avg_frequency_score,
            by_type=by_type,
            by_confidence=by_confidence,
            by_scope=by_scope,
            top_recurring=top_recurring,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("incident_pattern_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.pattern_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "max_recurring_pct": self._max_recurring_pct,
            "pattern_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
