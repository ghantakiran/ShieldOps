"""Forensic Timeline Builder — multi-source forensic timelines."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TimelineSource(StrEnum):
    SYSTEM_LOG = "system_log"
    NETWORK_LOG = "network_log"
    APPLICATION_LOG = "application_log"
    SECURITY_LOG = "security_log"
    CLOUD_AUDIT = "cloud_audit"


class EventSignificance(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"


class CorrelationConfidence(StrEnum):
    CONFIRMED = "confirmed"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCONFIRMED = "unconfirmed"


# --- Models ---


class TimelineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_name: str = ""
    timeline_source: TimelineSource = TimelineSource.SYSTEM_LOG
    event_significance: EventSignificance = EventSignificance.CRITICAL
    correlation_confidence: CorrelationConfidence = CorrelationConfidence.CONFIRMED
    accuracy_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TimelineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_name: str = ""
    timeline_source: TimelineSource = TimelineSource.SYSTEM_LOG
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TimelineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_accuracy_count: int = 0
    avg_accuracy_score: float = 0.0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_significance: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_low_accuracy: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ForensicTimelineBuilder:
    """Build multi-source forensic timelines for incident investigation."""

    def __init__(
        self,
        max_records: int = 200000,
        accuracy_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._accuracy_threshold = accuracy_threshold
        self._records: list[TimelineRecord] = []
        self._analyses: list[TimelineAnalysis] = []
        logger.info(
            "forensic_timeline_builder.initialized",
            max_records=max_records,
            accuracy_threshold=accuracy_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_event(
        self,
        event_name: str,
        timeline_source: TimelineSource = TimelineSource.SYSTEM_LOG,
        event_significance: EventSignificance = EventSignificance.CRITICAL,
        correlation_confidence: CorrelationConfidence = CorrelationConfidence.CONFIRMED,
        accuracy_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TimelineRecord:
        record = TimelineRecord(
            event_name=event_name,
            timeline_source=timeline_source,
            event_significance=event_significance,
            correlation_confidence=correlation_confidence,
            accuracy_score=accuracy_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "forensic_timeline_builder.event_recorded",
            record_id=record.id,
            event_name=event_name,
            timeline_source=timeline_source.value,
            event_significance=event_significance.value,
        )
        return record

    def get_event(self, record_id: str) -> TimelineRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_events(
        self,
        timeline_source: TimelineSource | None = None,
        event_significance: EventSignificance | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TimelineRecord]:
        results = list(self._records)
        if timeline_source is not None:
            results = [r for r in results if r.timeline_source == timeline_source]
        if event_significance is not None:
            results = [r for r in results if r.event_significance == event_significance]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        event_name: str,
        timeline_source: TimelineSource = TimelineSource.SYSTEM_LOG,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TimelineAnalysis:
        analysis = TimelineAnalysis(
            event_name=event_name,
            timeline_source=timeline_source,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "forensic_timeline_builder.analysis_added",
            event_name=event_name,
            timeline_source=timeline_source.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_event_distribution(self) -> dict[str, Any]:
        """Group by timeline_source; return count and avg accuracy_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.timeline_source.value
            src_data.setdefault(key, []).append(r.accuracy_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_accuracy_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_accuracy_events(self) -> list[dict[str, Any]]:
        """Return records where accuracy_score < accuracy_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.accuracy_score < self._accuracy_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "event_name": r.event_name,
                        "timeline_source": r.timeline_source.value,
                        "accuracy_score": r.accuracy_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["accuracy_score"])

    def rank_by_accuracy(self) -> list[dict[str, Any]]:
        """Group by service, avg accuracy_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.accuracy_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_accuracy_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_accuracy_score"])
        return results

    def detect_timeline_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> TimelineReport:
        by_source: dict[str, int] = {}
        by_significance: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_source[r.timeline_source.value] = by_source.get(r.timeline_source.value, 0) + 1
            by_significance[r.event_significance.value] = (
                by_significance.get(r.event_significance.value, 0) + 1
            )
            by_confidence[r.correlation_confidence.value] = (
                by_confidence.get(r.correlation_confidence.value, 0) + 1
            )
        low_accuracy_count = sum(
            1 for r in self._records if r.accuracy_score < self._accuracy_threshold
        )
        scores = [r.accuracy_score for r in self._records]
        avg_accuracy_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_accuracy_events()
        top_low_accuracy = [o["event_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_accuracy_count > 0:
            recs.append(
                f"{low_accuracy_count} event(s) below accuracy threshold "
                f"({self._accuracy_threshold})"
            )
        if self._records and avg_accuracy_score < self._accuracy_threshold:
            recs.append(
                f"Avg accuracy score {avg_accuracy_score} below threshold "
                f"({self._accuracy_threshold})"
            )
        if not recs:
            recs.append("Forensic timeline accuracy is healthy")
        return TimelineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_accuracy_count=low_accuracy_count,
            avg_accuracy_score=avg_accuracy_score,
            by_source=by_source,
            by_significance=by_significance,
            by_confidence=by_confidence,
            top_low_accuracy=top_low_accuracy,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("forensic_timeline_builder.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        source_dist: dict[str, int] = {}
        for r in self._records:
            key = r.timeline_source.value
            source_dist[key] = source_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "accuracy_threshold": self._accuracy_threshold,
            "source_distribution": source_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
