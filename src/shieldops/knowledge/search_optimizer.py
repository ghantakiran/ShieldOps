"""Knowledge Search Optimizer — optimize search relevance and usage patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SearchQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    NO_RESULTS = "no_results"


class ContentType(StrEnum):
    RUNBOOK = "runbook"
    PLAYBOOK = "playbook"
    POSTMORTEM = "postmortem"
    FAQ = "faq"
    TROUBLESHOOTING = "troubleshooting"


class UsageFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    RARELY = "rarely"
    NEVER = "never"


# --- Models ---


class SearchRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str = ""
    content_type: ContentType = ContentType.RUNBOOK
    search_quality: SearchQuality = SearchQuality.ADEQUATE
    usage_frequency: UsageFrequency = UsageFrequency.MONTHLY
    relevance_score: float = 0.0
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class SearchPattern(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query_pattern: str = ""
    content_type: ContentType = ContentType.RUNBOOK
    search_quality: SearchQuality = SearchQuality.ADEQUATE
    hit_count: int = 0
    avg_relevance: float = 0.0
    created_at: float = Field(default_factory=time.time)


class KnowledgeSearchReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_patterns: int = 0
    poor_search_count: int = 0
    avg_relevance_score: float = 0.0
    by_quality: dict[str, int] = Field(default_factory=dict)
    by_content: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    low_relevance_queries: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeSearchOptimizer:
    """Optimize knowledge base search relevance and usage patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        min_relevance_score: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_relevance_score = min_relevance_score
        self._records: list[SearchRecord] = []
        self._patterns: list[SearchPattern] = []
        logger.info(
            "knowledge_search.initialized",
            max_records=max_records,
            min_relevance_score=min_relevance_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_search(
        self,
        query: str,
        content_type: ContentType = ContentType.RUNBOOK,
        search_quality: SearchQuality = SearchQuality.ADEQUATE,
        usage_frequency: UsageFrequency = UsageFrequency.MONTHLY,
        relevance_score: float = 0.0,
        team: str = "",
        details: str = "",
    ) -> SearchRecord:
        record = SearchRecord(
            query=query,
            content_type=content_type,
            search_quality=search_quality,
            usage_frequency=usage_frequency,
            relevance_score=relevance_score,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_search.search_recorded",
            record_id=record.id,
            query=query,
            content_type=content_type.value,
            search_quality=search_quality.value,
        )
        return record

    def get_search(self, record_id: str) -> SearchRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_searches(
        self,
        content_type: ContentType | None = None,
        quality: SearchQuality | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SearchRecord]:
        results = list(self._records)
        if content_type is not None:
            results = [r for r in results if r.content_type == content_type]
        if quality is not None:
            results = [r for r in results if r.search_quality == quality]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_pattern(
        self,
        query_pattern: str,
        content_type: ContentType = ContentType.RUNBOOK,
        search_quality: SearchQuality = SearchQuality.ADEQUATE,
        hit_count: int = 0,
        avg_relevance: float = 0.0,
    ) -> SearchPattern:
        pattern = SearchPattern(
            query_pattern=query_pattern,
            content_type=content_type,
            search_quality=search_quality,
            hit_count=hit_count,
            avg_relevance=avg_relevance,
        )
        self._patterns.append(pattern)
        if len(self._patterns) > self._max_records:
            self._patterns = self._patterns[-self._max_records :]
        logger.info(
            "knowledge_search.pattern_added",
            query_pattern=query_pattern,
            content_type=content_type.value,
            hit_count=hit_count,
        )
        return pattern

    # -- domain operations --------------------------------------------------

    def analyze_search_quality(self) -> dict[str, Any]:
        """Group by quality; return count and avg relevance per quality."""
        quality_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.search_quality.value
            quality_data.setdefault(key, []).append(r.relevance_score)
        result: dict[str, Any] = {}
        for quality, scores in quality_data.items():
            result[quality] = {
                "count": len(scores),
                "avg_relevance": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_poor_searches(self) -> list[dict[str, Any]]:
        """Return searches where quality is POOR or NO_RESULTS."""
        poor_qualities = {
            SearchQuality.POOR,
            SearchQuality.NO_RESULTS,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.search_quality in poor_qualities:
                results.append(
                    {
                        "record_id": r.id,
                        "query": r.query,
                        "search_quality": r.search_quality.value,
                        "content_type": r.content_type.value,
                        "relevance_score": r.relevance_score,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["relevance_score"], reverse=False)
        return results

    def rank_by_relevance(self) -> list[dict[str, Any]]:
        """Group by content_type, avg relevance, sort desc."""
        type_scores: dict[str, list[float]] = {}
        for r in self._records:
            type_scores.setdefault(r.content_type.value, []).append(r.relevance_score)
        results: list[dict[str, Any]] = []
        for ctype, scores in type_scores.items():
            results.append(
                {
                    "content_type": ctype,
                    "avg_relevance": round(sum(scores) / len(scores), 2),
                    "search_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_relevance"], reverse=True)
        return results

    def detect_search_trends(self) -> dict[str, Any]:
        """Split-half comparison on relevance_scores; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [r.relevance_score for r in self._records]
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

    def generate_report(self) -> KnowledgeSearchReport:
        by_quality: dict[str, int] = {}
        by_content: dict[str, int] = {}
        by_frequency: dict[str, int] = {}
        for r in self._records:
            by_quality[r.search_quality.value] = by_quality.get(r.search_quality.value, 0) + 1
            by_content[r.content_type.value] = by_content.get(r.content_type.value, 0) + 1
            by_frequency[r.usage_frequency.value] = by_frequency.get(r.usage_frequency.value, 0) + 1
        poor_search_count = sum(
            1
            for r in self._records
            if r.search_quality in {SearchQuality.POOR, SearchQuality.NO_RESULTS}
        )
        avg_relevance = (
            round(
                sum(r.relevance_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        poor = self.identify_poor_searches()
        low_relevance_queries = [p["query"] for p in poor]
        recs: list[str] = []
        if poor:
            recs.append(f"{len(poor)} poor search(es) detected — review content gaps")
        low_rel = sum(1 for r in self._records if r.relevance_score < self._min_relevance_score)
        if low_rel > 0:
            recs.append(
                f"{low_rel} search(es) below relevance threshold ({self._min_relevance_score}%)"
            )
        if not recs:
            recs.append("Search relevance levels are acceptable")
        return KnowledgeSearchReport(
            total_records=len(self._records),
            total_patterns=len(self._patterns),
            poor_search_count=poor_search_count,
            avg_relevance_score=avg_relevance,
            by_quality=by_quality,
            by_content=by_content,
            by_frequency=by_frequency,
            low_relevance_queries=low_relevance_queries,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._patterns.clear()
        logger.info("knowledge_search.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        quality_dist: dict[str, int] = {}
        for r in self._records:
            key = r.search_quality.value
            quality_dist[key] = quality_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_patterns": len(self._patterns),
            "min_relevance_score": self._min_relevance_score,
            "quality_distribution": quality_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_queries": len({r.query for r in self._records}),
        }
