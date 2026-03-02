"""Threat Intel Correlation — multi-feed TI correlation, emerging threats."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IntelFeed(StrEnum):
    OPEN_SOURCE = "open_source"
    COMMERCIAL = "commercial"
    GOVERNMENT = "government"
    ISAC = "isac"
    INTERNAL = "internal"


class CorrelationType(StrEnum):
    IOC_MATCH = "ioc_match"
    TTP_OVERLAP = "ttp_overlap"
    CAMPAIGN_LINK = "campaign_link"
    INFRASTRUCTURE_OVERLAP = "infrastructure_overlap"
    BEHAVIORAL_MATCH = "behavioral_match"


class ThreatCategory(StrEnum):
    NATION_STATE = "nation_state"
    CYBERCRIME = "cybercrime"
    HACKTIVISM = "hacktivism"
    INSIDER = "insider"
    UNKNOWN = "unknown"


# --- Models ---


class CorrelationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_name: str = ""
    intel_feed: IntelFeed = IntelFeed.OPEN_SOURCE
    correlation_type: CorrelationType = CorrelationType.IOC_MATCH
    threat_category: ThreatCategory = ThreatCategory.NATION_STATE
    correlation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CorrelationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_name: str = ""
    intel_feed: IntelFeed = IntelFeed.OPEN_SOURCE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ThreatIntelReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_confidence_count: int = 0
    avg_correlation_score: float = 0.0
    by_feed: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_low_confidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThreatIntelCorrelation:
    """Multi-feed threat intelligence correlation and emerging threat detection."""

    def __init__(
        self,
        max_records: int = 200000,
        correlation_confidence_threshold: float = 65.0,
    ) -> None:
        self._max_records = max_records
        self._correlation_confidence_threshold = correlation_confidence_threshold
        self._records: list[CorrelationRecord] = []
        self._analyses: list[CorrelationAnalysis] = []
        logger.info(
            "threat_intel_correlation.initialized",
            max_records=max_records,
            correlation_confidence_threshold=correlation_confidence_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_correlation(
        self,
        correlation_name: str,
        intel_feed: IntelFeed = IntelFeed.OPEN_SOURCE,
        correlation_type: CorrelationType = CorrelationType.IOC_MATCH,
        threat_category: ThreatCategory = ThreatCategory.NATION_STATE,
        correlation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CorrelationRecord:
        record = CorrelationRecord(
            correlation_name=correlation_name,
            intel_feed=intel_feed,
            correlation_type=correlation_type,
            threat_category=threat_category,
            correlation_score=correlation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "threat_intel_correlation.correlation_recorded",
            record_id=record.id,
            correlation_name=correlation_name,
            intel_feed=intel_feed.value,
            correlation_type=correlation_type.value,
        )
        return record

    def get_correlation(self, record_id: str) -> CorrelationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_correlations(
        self,
        intel_feed: IntelFeed | None = None,
        correlation_type: CorrelationType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CorrelationRecord]:
        results = list(self._records)
        if intel_feed is not None:
            results = [r for r in results if r.intel_feed == intel_feed]
        if correlation_type is not None:
            results = [r for r in results if r.correlation_type == correlation_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        correlation_name: str,
        intel_feed: IntelFeed = IntelFeed.OPEN_SOURCE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CorrelationAnalysis:
        analysis = CorrelationAnalysis(
            correlation_name=correlation_name,
            intel_feed=intel_feed,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "threat_intel_correlation.analysis_added",
            correlation_name=correlation_name,
            intel_feed=intel_feed.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_feed_distribution(self) -> dict[str, Any]:
        """Group by intel_feed; return count and avg correlation_score."""
        feed_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.intel_feed.value
            feed_data.setdefault(key, []).append(r.correlation_score)
        result: dict[str, Any] = {}
        for feed, scores in feed_data.items():
            result[feed] = {
                "count": len(scores),
                "avg_correlation_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_confidence_correlations(self) -> list[dict[str, Any]]:
        """Return records where correlation_score < correlation_confidence_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.correlation_score < self._correlation_confidence_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "correlation_name": r.correlation_name,
                        "intel_feed": r.intel_feed.value,
                        "correlation_score": r.correlation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["correlation_score"])

    def rank_by_correlation_score(self) -> list[dict[str, Any]]:
        """Group by service, avg correlation_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.correlation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_correlation_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_correlation_score"])
        return results

    def detect_correlation_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> ThreatIntelReport:
        by_feed: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_feed[r.intel_feed.value] = by_feed.get(r.intel_feed.value, 0) + 1
            by_type[r.correlation_type.value] = by_type.get(r.correlation_type.value, 0) + 1
            by_category[r.threat_category.value] = by_category.get(r.threat_category.value, 0) + 1
        low_confidence_count = sum(
            1 for r in self._records if r.correlation_score < self._correlation_confidence_threshold
        )
        scores = [r.correlation_score for r in self._records]
        avg_correlation_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_confidence_correlations()
        top_low_confidence = [o["correlation_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_confidence_count > 0:
            recs.append(
                f"{low_confidence_count} correlation(s) below confidence threshold "
                f"({self._correlation_confidence_threshold})"
            )
        if self._records and avg_correlation_score < self._correlation_confidence_threshold:
            recs.append(
                f"Avg correlation score {avg_correlation_score} below threshold "
                f"({self._correlation_confidence_threshold})"
            )
        if not recs:
            recs.append("Threat intel correlation confidence is healthy")
        return ThreatIntelReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_confidence_count=low_confidence_count,
            avg_correlation_score=avg_correlation_score,
            by_feed=by_feed,
            by_type=by_type,
            by_category=by_category,
            top_low_confidence=top_low_confidence,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("threat_intel_correlation.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        feed_dist: dict[str, int] = {}
        for r in self._records:
            key = r.intel_feed.value
            feed_dist[key] = feed_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "correlation_confidence_threshold": self._correlation_confidence_threshold,
            "feed_distribution": feed_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
