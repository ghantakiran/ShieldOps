"""Knowledge Usage Analyzer — analyze article usage, identify underused content."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class UsageType(StrEnum):
    VIEW = "view"
    SEARCH = "search"
    REFERENCE = "reference"
    SHARE = "share"
    FEEDBACK = "feedback"


class ContentCategory(StrEnum):
    RUNBOOK = "runbook"
    POSTMORTEM = "postmortem"
    FAQ = "faq"
    ARCHITECTURE = "architecture"
    TROUBLESHOOTING = "troubleshooting"


class UsageTrend(StrEnum):
    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"
    SEASONAL = "seasonal"
    NEW = "new"


# --- Models ---


class UsageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    article_id: str = ""
    usage_type: UsageType = UsageType.VIEW
    content_category: ContentCategory = ContentCategory.RUNBOOK
    usage_trend: UsageTrend = UsageTrend.NEW
    view_count: int = 0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class UsageRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category_pattern: str = ""
    content_category: ContentCategory = ContentCategory.RUNBOOK
    min_views: int = 0
    stale_after_days: int = 90
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class UsageAnalysisReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    active_articles: int = 0
    avg_view_count: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    underused: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeUsageAnalyzer:
    """Analyze knowledge base usage, identify underused content, track trends."""

    def __init__(
        self,
        max_records: int = 200000,
        min_usage_score: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._min_usage_score = min_usage_score
        self._records: list[UsageRecord] = []
        self._rules: list[UsageRule] = []
        logger.info(
            "usage_analyzer.initialized",
            max_records=max_records,
            min_usage_score=min_usage_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_usage(
        self,
        article_id: str,
        usage_type: UsageType = UsageType.VIEW,
        content_category: ContentCategory = ContentCategory.RUNBOOK,
        usage_trend: UsageTrend = UsageTrend.NEW,
        view_count: int = 0,
        team: str = "",
    ) -> UsageRecord:
        record = UsageRecord(
            article_id=article_id,
            usage_type=usage_type,
            content_category=content_category,
            usage_trend=usage_trend,
            view_count=view_count,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "usage_analyzer.usage_recorded",
            record_id=record.id,
            article_id=article_id,
            usage_type=usage_type.value,
            content_category=content_category.value,
        )
        return record

    def get_usage(self, record_id: str) -> UsageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_usages(
        self,
        usage_type: UsageType | None = None,
        content_category: ContentCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[UsageRecord]:
        results = list(self._records)
        if usage_type is not None:
            results = [r for r in results if r.usage_type == usage_type]
        if content_category is not None:
            results = [r for r in results if r.content_category == content_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        category_pattern: str,
        content_category: ContentCategory = ContentCategory.RUNBOOK,
        min_views: int = 0,
        stale_after_days: int = 90,
        description: str = "",
    ) -> UsageRule:
        rule = UsageRule(
            category_pattern=category_pattern,
            content_category=content_category,
            min_views=min_views,
            stale_after_days=stale_after_days,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "usage_analyzer.rule_added",
            category_pattern=category_pattern,
            content_category=content_category.value,
            min_views=min_views,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_usage_patterns(self) -> dict[str, Any]:
        """Group by usage_type; return count and avg view_count per type."""
        type_data: dict[str, list[int]] = {}
        for r in self._records:
            key = r.usage_type.value
            type_data.setdefault(key, []).append(r.view_count)
        result: dict[str, Any] = {}
        for utype, counts in type_data.items():
            result[utype] = {
                "count": len(counts),
                "avg_view_count": round(sum(counts) / len(counts), 2),
            }
        return result

    def identify_underused(self) -> list[dict[str, Any]]:
        """Return records where view_count < min_usage_score."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.view_count < self._min_usage_score:
                results.append(
                    {
                        "record_id": r.id,
                        "article_id": r.article_id,
                        "view_count": r.view_count,
                        "content_category": r.content_category.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_views(self) -> list[dict[str, Any]]:
        """Group by team, total view_count, sort descending."""
        team_views: dict[str, int] = {}
        for r in self._records:
            team_views[r.team] = team_views.get(r.team, 0) + r.view_count
        results: list[dict[str, Any]] = []
        for team, total in team_views.items():
            results.append(
                {
                    "team": team,
                    "total_views": total,
                }
            )
        results.sort(key=lambda x: x["total_views"], reverse=True)
        return results

    def detect_usage_trends(self) -> dict[str, Any]:
        """Split-half on view_count; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [r.view_count for r in self._records]
        mid = len(counts) // 2
        first_half = counts[:mid]
        second_half = counts[mid:]
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

    def generate_report(self) -> UsageAnalysisReport:
        by_type: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_trend: dict[str, int] = {}
        for r in self._records:
            by_type[r.usage_type.value] = by_type.get(r.usage_type.value, 0) + 1
            by_category[r.content_category.value] = by_category.get(r.content_category.value, 0) + 1
            by_trend[r.usage_trend.value] = by_trend.get(r.usage_trend.value, 0) + 1
        underused_count = sum(1 for r in self._records if r.view_count < self._min_usage_score)
        active_articles = len({r.article_id for r in self._records if r.view_count > 0})
        avg_view = (
            round(sum(r.view_count for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        underused_ids = [
            r.article_id for r in self._records if r.view_count < self._min_usage_score
        ][:5]
        recs: list[str] = []
        if underused_count > 0:
            recs.append(
                f"{underused_count} article(s) below minimum usage score ({self._min_usage_score})"
            )
        if self._records and avg_view < self._min_usage_score:
            recs.append(
                f"Average view count {avg_view} is below threshold ({self._min_usage_score})"
            )
        if not recs:
            recs.append("Knowledge usage levels are healthy")
        return UsageAnalysisReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            active_articles=active_articles,
            avg_view_count=avg_view,
            by_type=by_type,
            by_category=by_category,
            by_trend=by_trend,
            underused=underused_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("usage_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.usage_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "min_usage_score": self._min_usage_score,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_articles": len({r.article_id for r in self._records}),
        }
