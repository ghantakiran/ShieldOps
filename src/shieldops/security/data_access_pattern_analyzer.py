"""Data Access Pattern Analyzer — analyze data access patterns to detect anomalies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AccessPattern(StrEnum):
    NORMAL = "normal"
    BULK_READ = "bulk_read"
    OFF_HOURS = "off_hours"
    NEW_RESOURCE = "new_resource"
    PRIVILEGE_ESCALATION = "privilege_escalation"


class PatternSource(StrEnum):
    AUDIT_LOG = "audit_log"
    DLP = "dlp"
    DATABASE_MONITOR = "database_monitor"
    API_GATEWAY = "api_gateway"
    IDENTITY_PROVIDER = "identity_provider"


class PatternRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BASELINE = "baseline"


# --- Models ---


class AccessPatternRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    access_pattern: AccessPattern = AccessPattern.NORMAL
    pattern_source: PatternSource = PatternSource.AUDIT_LOG
    pattern_risk: PatternRisk = PatternRisk.LOW
    pattern_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AccessPatternAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    access_pattern: AccessPattern = AccessPattern.NORMAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AccessPatternReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_pattern_score: float = 0.0
    by_pattern: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataAccessPatternAnalyzer:
    """Analyze data access patterns to detect anomalies and insider threats."""

    def __init__(
        self,
        max_records: int = 200000,
        pattern_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._pattern_threshold = pattern_threshold
        self._records: list[AccessPatternRecord] = []
        self._analyses: list[AccessPatternAnalysis] = []
        logger.info(
            "data_access_pattern_analyzer.initialized",
            max_records=max_records,
            pattern_threshold=pattern_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_pattern(
        self,
        pattern_id: str,
        access_pattern: AccessPattern = AccessPattern.NORMAL,
        pattern_source: PatternSource = PatternSource.AUDIT_LOG,
        pattern_risk: PatternRisk = PatternRisk.LOW,
        pattern_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AccessPatternRecord:
        record = AccessPatternRecord(
            pattern_id=pattern_id,
            access_pattern=access_pattern,
            pattern_source=pattern_source,
            pattern_risk=pattern_risk,
            pattern_score=pattern_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_access_pattern_analyzer.pattern_recorded",
            record_id=record.id,
            pattern_id=pattern_id,
            access_pattern=access_pattern.value,
            pattern_source=pattern_source.value,
        )
        return record

    def get_pattern(self, record_id: str) -> AccessPatternRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_patterns(
        self,
        access_pattern: AccessPattern | None = None,
        pattern_source: PatternSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AccessPatternRecord]:
        results = list(self._records)
        if access_pattern is not None:
            results = [r for r in results if r.access_pattern == access_pattern]
        if pattern_source is not None:
            results = [r for r in results if r.pattern_source == pattern_source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        pattern_id: str,
        access_pattern: AccessPattern = AccessPattern.NORMAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AccessPatternAnalysis:
        analysis = AccessPatternAnalysis(
            pattern_id=pattern_id,
            access_pattern=access_pattern,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "data_access_pattern_analyzer.analysis_added",
            pattern_id=pattern_id,
            access_pattern=access_pattern.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_pattern_distribution(self) -> dict[str, Any]:
        pattern_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.access_pattern.value
            pattern_data.setdefault(key, []).append(r.pattern_score)
        result: dict[str, Any] = {}
        for pattern, scores in pattern_data.items():
            result[pattern] = {
                "count": len(scores),
                "avg_pattern_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_pattern_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.pattern_score < self._pattern_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "pattern_id": r.pattern_id,
                        "access_pattern": r.access_pattern.value,
                        "pattern_score": r.pattern_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["pattern_score"])

    def rank_by_pattern(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.pattern_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_pattern_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_pattern_score"])
        return results

    def detect_pattern_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AccessPatternReport:
        by_pattern: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_pattern[r.access_pattern.value] = by_pattern.get(r.access_pattern.value, 0) + 1
            by_source[r.pattern_source.value] = by_source.get(r.pattern_source.value, 0) + 1
            by_risk[r.pattern_risk.value] = by_risk.get(r.pattern_risk.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.pattern_score < self._pattern_threshold)
        scores = [r.pattern_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_pattern_gaps()
        top_gaps = [o["pattern_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} pattern(s) below threshold ({self._pattern_threshold})")
        if self._records and avg_score < self._pattern_threshold:
            recs.append(
                f"Avg pattern score {avg_score} below threshold ({self._pattern_threshold})"
            )
        if not recs:
            recs.append("Data access pattern analysis is healthy")
        return AccessPatternReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_pattern_score=avg_score,
            by_pattern=by_pattern,
            by_source=by_source,
            by_risk=by_risk,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("data_access_pattern_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        pattern_dist: dict[str, int] = {}
        for r in self._records:
            key = r.access_pattern.value
            pattern_dist[key] = pattern_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "pattern_threshold": self._pattern_threshold,
            "pattern_distribution": pattern_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
