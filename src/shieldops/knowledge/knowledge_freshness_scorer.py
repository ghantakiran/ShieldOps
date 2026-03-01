"""Knowledge Freshness Scorer — score knowledge article freshness, detect stale documentation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FreshnessLevel(StrEnum):
    CURRENT = "current"
    RECENT = "recent"
    AGING = "aging"
    STALE = "stale"
    OBSOLETE = "obsolete"


class ArticleType(StrEnum):
    RUNBOOK = "runbook"
    PLAYBOOK = "playbook"
    FAQ = "faq"
    ARCHITECTURE = "architecture"
    ONBOARDING = "onboarding"


class UpdateFrequency(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    NEVER = "never"


# --- Models ---


class FreshnessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    article_id: str = ""
    freshness_level: FreshnessLevel = FreshnessLevel.CURRENT
    article_type: ArticleType = ArticleType.RUNBOOK
    update_frequency: UpdateFrequency = UpdateFrequency.MONTHLY
    freshness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FreshnessMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    article_id: str = ""
    freshness_level: FreshnessLevel = FreshnessLevel.CURRENT
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeFreshnessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    stale_count: int = 0
    avg_freshness_score: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    top_stale: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeFreshnessScorer:
    """Score knowledge article freshness, detect stale documentation."""

    def __init__(
        self,
        max_records: int = 200000,
        min_freshness_score: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_freshness_score = min_freshness_score
        self._records: list[FreshnessRecord] = []
        self._metrics: list[FreshnessMetric] = []
        logger.info(
            "knowledge_freshness_scorer.initialized",
            max_records=max_records,
            min_freshness_score=min_freshness_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_freshness(
        self,
        article_id: str,
        freshness_level: FreshnessLevel = FreshnessLevel.CURRENT,
        article_type: ArticleType = ArticleType.RUNBOOK,
        update_frequency: UpdateFrequency = UpdateFrequency.MONTHLY,
        freshness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> FreshnessRecord:
        record = FreshnessRecord(
            article_id=article_id,
            freshness_level=freshness_level,
            article_type=article_type,
            update_frequency=update_frequency,
            freshness_score=freshness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_freshness_scorer.freshness_recorded",
            record_id=record.id,
            article_id=article_id,
            freshness_level=freshness_level.value,
            article_type=article_type.value,
        )
        return record

    def get_freshness(self, record_id: str) -> FreshnessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_freshness(
        self,
        level: FreshnessLevel | None = None,
        article_type: ArticleType | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FreshnessRecord]:
        results = list(self._records)
        if level is not None:
            results = [r for r in results if r.freshness_level == level]
        if article_type is not None:
            results = [r for r in results if r.article_type == article_type]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        article_id: str,
        freshness_level: FreshnessLevel = FreshnessLevel.CURRENT,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FreshnessMetric:
        metric = FreshnessMetric(
            article_id=article_id,
            freshness_level=freshness_level,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "knowledge_freshness_scorer.metric_added",
            article_id=article_id,
            freshness_level=freshness_level.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_freshness_distribution(self) -> dict[str, Any]:
        """Group by freshness_level; return count and avg freshness_score."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.freshness_level.value
            level_data.setdefault(key, []).append(r.freshness_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_freshness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_stale_articles(self) -> list[dict[str, Any]]:
        """Return records where freshness_level is STALE or OBSOLETE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.freshness_level in (FreshnessLevel.STALE, FreshnessLevel.OBSOLETE):
                results.append(
                    {
                        "record_id": r.id,
                        "article_id": r.article_id,
                        "freshness_level": r.freshness_level.value,
                        "freshness_score": r.freshness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_freshness(self) -> list[dict[str, Any]]:
        """Group by service, avg freshness_score, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.freshness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_freshness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_freshness_score"])
        return results

    def detect_freshness_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [m.metric_score for m in self._metrics]
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

    def generate_report(self) -> KnowledgeFreshnessReport:
        by_level: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_frequency: dict[str, int] = {}
        for r in self._records:
            by_level[r.freshness_level.value] = by_level.get(r.freshness_level.value, 0) + 1
            by_type[r.article_type.value] = by_type.get(r.article_type.value, 0) + 1
            by_frequency[r.update_frequency.value] = (
                by_frequency.get(r.update_frequency.value, 0) + 1
            )
        stale_count = sum(
            1
            for r in self._records
            if r.freshness_level in (FreshnessLevel.STALE, FreshnessLevel.OBSOLETE)
        )
        scores = [r.freshness_score for r in self._records]
        avg_freshness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        stale_list = self.identify_stale_articles()
        top_stale = [s["article_id"] for s in stale_list[:5]]
        recs: list[str] = []
        if self._records and avg_freshness_score < self._min_freshness_score:
            recs.append(
                f"Avg freshness score {avg_freshness_score} below threshold "
                f"({self._min_freshness_score})"
            )
        if stale_count > 0:
            recs.append(f"{stale_count} stale article(s) — review and update")
        if not recs:
            recs.append("Knowledge freshness levels are healthy")
        return KnowledgeFreshnessReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            stale_count=stale_count,
            avg_freshness_score=avg_freshness_score,
            by_level=by_level,
            by_type=by_type,
            by_frequency=by_frequency,
            top_stale=top_stale,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("knowledge_freshness_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.freshness_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_freshness_score": self._min_freshness_score,
            "freshness_level_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
