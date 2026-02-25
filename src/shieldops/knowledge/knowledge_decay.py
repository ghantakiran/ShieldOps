"""Knowledge Decay Detector — detect knowledge staleness and accuracy decay."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DecayRisk(StrEnum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    DECAYED = "decayed"
    OBSOLETE = "obsolete"


class ArticleType(StrEnum):
    RUNBOOK = "runbook"
    TROUBLESHOOTING = "troubleshooting"
    ARCHITECTURE = "architecture"
    ONBOARDING = "onboarding"
    POSTMORTEM = "postmortem"


class DecaySignal(StrEnum):
    AGE = "age"
    INFRA_CHANGE = "infra_change"
    SERVICE_DEPRECATED = "service_deprecated"
    NEGATIVE_FEEDBACK = "negative_feedback"
    LOW_USAGE = "low_usage"


# --- Models ---


class KnowledgeDecayRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    article_id: str = ""
    article_title: str = ""
    article_type: ArticleType = ArticleType.RUNBOOK
    decay_risk: DecayRisk = DecayRisk.FRESH
    decay_score: float = 0.0
    signals: list[str] = Field(default_factory=list)
    age_days: int = 0
    last_reviewed_days_ago: int = 0
    usage_count_30d: int = 0
    created_at: float = Field(default_factory=time.time)


class DecayThreshold(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    article_type: ArticleType = ArticleType.RUNBOOK
    stale_days: int = 180
    obsolete_days: int = 365
    min_usage_30d: int = 1
    created_at: float = Field(default_factory=time.time)


class KnowledgeDecayReport(BaseModel):
    total_assessments: int = 0
    stale_count: int = 0
    obsolete_count: int = 0
    by_risk: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    top_decay_signals: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeDecayDetector:
    """Detect knowledge staleness and accuracy decay as infrastructure evolves."""

    def __init__(
        self,
        max_records: int = 200000,
        stale_days: int = 180,
    ) -> None:
        self._max_records = max_records
        self._stale_days = stale_days
        self._records: list[KnowledgeDecayRecord] = []
        self._thresholds: dict[str, DecayThreshold] = {}
        logger.info(
            "knowledge_decay.initialized",
            max_records=max_records,
            stale_days=stale_days,
        )

    # -- internal helpers ------------------------------------------------

    def _score_to_risk(self, score: float) -> DecayRisk:
        if score < 0.2:
            return DecayRisk.FRESH
        if score < 0.4:
            return DecayRisk.AGING
        if score < 0.6:
            return DecayRisk.STALE
        if score < 0.8:
            return DecayRisk.DECAYED
        return DecayRisk.OBSOLETE

    def _calculate_decay(
        self,
        age_days: int,
        last_reviewed_days_ago: int,
        usage_count_30d: int,
        signals: list[str],
    ) -> float:
        """Calculate decay score from 0 to 1."""
        age_factor = min(1.0, age_days / (self._stale_days * 2))
        review_factor = min(1.0, last_reviewed_days_ago / self._stale_days)
        usage_factor = max(0, 1.0 - usage_count_30d / 10) if usage_count_30d < 10 else 0.0
        signal_factor = min(0.3, len(signals) * 0.1)
        score = round(
            age_factor * 0.3 + review_factor * 0.3 + usage_factor * 0.2 + signal_factor,
            4,
        )
        return min(1.0, score)

    # -- record / get / list ---------------------------------------------

    def assess_decay(
        self,
        article_id: str,
        article_title: str = "",
        article_type: ArticleType = ArticleType.RUNBOOK,
        age_days: int = 0,
        last_reviewed_days_ago: int = 0,
        usage_count_30d: int = 0,
        signals: list[str] | None = None,
    ) -> KnowledgeDecayRecord:
        signal_list = signals or []
        # Auto-add signals based on thresholds
        if age_days > self._stale_days and DecaySignal.AGE.value not in signal_list:
            signal_list.append(DecaySignal.AGE.value)
        if usage_count_30d == 0 and DecaySignal.LOW_USAGE.value not in signal_list:
            signal_list.append(DecaySignal.LOW_USAGE.value)

        decay_score = self._calculate_decay(
            age_days,
            last_reviewed_days_ago,
            usage_count_30d,
            signal_list,
        )
        decay_risk = self._score_to_risk(decay_score)

        record = KnowledgeDecayRecord(
            article_id=article_id,
            article_title=article_title,
            article_type=article_type,
            decay_risk=decay_risk,
            decay_score=decay_score,
            signals=signal_list,
            age_days=age_days,
            last_reviewed_days_ago=last_reviewed_days_ago,
            usage_count_30d=usage_count_30d,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "knowledge_decay.decay_assessed",
            record_id=record.id,
            article_id=article_id,
            decay_risk=decay_risk.value,
            decay_score=decay_score,
        )
        return record

    def get_assessment(self, record_id: str) -> KnowledgeDecayRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_assessments(
        self,
        article_type: ArticleType | None = None,
        decay_risk: DecayRisk | None = None,
        limit: int = 50,
    ) -> list[KnowledgeDecayRecord]:
        results = list(self._records)
        if article_type is not None:
            results = [r for r in results if r.article_type == article_type]
        if decay_risk is not None:
            results = [r for r in results if r.decay_risk == decay_risk]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def set_threshold(
        self,
        article_type: ArticleType,
        stale_days: int = 180,
        obsolete_days: int = 365,
        min_usage_30d: int = 1,
    ) -> DecayThreshold:
        threshold = DecayThreshold(
            article_type=article_type,
            stale_days=stale_days,
            obsolete_days=obsolete_days,
            min_usage_30d=min_usage_30d,
        )
        self._thresholds[article_type.value] = threshold
        logger.info(
            "knowledge_decay.threshold_set",
            article_type=article_type.value,
            stale_days=stale_days,
        )
        return threshold

    def calculate_decay_score(self, article_id: str) -> dict[str, Any]:
        """Calculate decay score for a specific article from its latest assessment."""
        assessments = [r for r in self._records if r.article_id == article_id]
        if not assessments:
            return {"article_id": article_id, "found": False, "decay_score": 0.0}
        latest = assessments[-1]
        return {
            "article_id": article_id,
            "found": True,
            "decay_score": latest.decay_score,
            "decay_risk": latest.decay_risk.value,
            "age_days": latest.age_days,
            "signals": latest.signals,
        }

    def identify_obsolete_articles(self) -> list[dict[str, Any]]:
        """Find articles that are obsolete or decayed."""
        # Get latest assessment per article
        latest: dict[str, KnowledgeDecayRecord] = {}
        for r in self._records:
            latest[r.article_id] = r
        results: list[dict[str, Any]] = []
        for article_id, r in latest.items():
            if r.decay_risk in (DecayRisk.DECAYED, DecayRisk.OBSOLETE):
                results.append(
                    {
                        "article_id": article_id,
                        "article_title": r.article_title,
                        "article_type": r.article_type.value,
                        "decay_risk": r.decay_risk.value,
                        "decay_score": r.decay_score,
                        "age_days": r.age_days,
                    }
                )
        results.sort(key=lambda x: x["decay_score"], reverse=True)
        return results

    def prioritize_for_review(self) -> list[dict[str, Any]]:
        """Prioritize articles that need review most urgently."""
        latest: dict[str, KnowledgeDecayRecord] = {}
        for r in self._records:
            latest[r.article_id] = r
        items = sorted(latest.values(), key=lambda r: r.decay_score, reverse=True)
        return [
            {
                "article_id": r.article_id,
                "article_title": r.article_title,
                "article_type": r.article_type.value,
                "decay_risk": r.decay_risk.value,
                "decay_score": r.decay_score,
                "signals": r.signals,
            }
            for r in items
            if r.decay_risk not in (DecayRisk.FRESH,)
        ]

    def detect_deprecated_references(self) -> list[dict[str, Any]]:
        """Find articles referencing deprecated services."""
        deprecated = [r for r in self._records if DecaySignal.SERVICE_DEPRECATED.value in r.signals]
        return [
            {
                "article_id": r.article_id,
                "article_title": r.article_title,
                "article_type": r.article_type.value,
                "decay_score": r.decay_score,
            }
            for r in deprecated
        ]

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> KnowledgeDecayReport:
        by_risk: dict[str, int] = {}
        by_type: dict[str, int] = {}
        signal_counts: dict[str, int] = {}
        for r in self._records:
            by_risk[r.decay_risk.value] = by_risk.get(r.decay_risk.value, 0) + 1
            by_type[r.article_type.value] = by_type.get(r.article_type.value, 0) + 1
            for s in r.signals:
                signal_counts[s] = signal_counts.get(s, 0) + 1
        stale = sum(
            1 for r in self._records if r.decay_risk in (DecayRisk.STALE, DecayRisk.DECAYED)
        )
        obsolete = sum(1 for r in self._records if r.decay_risk == DecayRisk.OBSOLETE)
        recs: list[str] = []
        if obsolete > 0:
            recs.append(f"{obsolete} article(s) are obsolete — consider archiving")
        if stale > 0:
            recs.append(f"{stale} article(s) are stale — schedule review")
        deprecated_count = signal_counts.get(DecaySignal.SERVICE_DEPRECATED.value, 0)
        if deprecated_count > 0:
            recs.append(f"{deprecated_count} article(s) reference deprecated services")
        if not recs:
            recs.append("Knowledge base health is good")
        return KnowledgeDecayReport(
            total_assessments=len(self._records),
            stale_count=stale,
            obsolete_count=obsolete,
            by_risk=by_risk,
            by_type=by_type,
            top_decay_signals=signal_counts,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._thresholds.clear()
        logger.info("knowledge_decay.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        risk_dist: dict[str, int] = {}
        for r in self._records:
            key = r.decay_risk.value
            risk_dist[key] = risk_dist.get(key, 0) + 1
        return {
            "total_assessments": len(self._records),
            "total_thresholds": len(self._thresholds),
            "stale_days": self._stale_days,
            "risk_distribution": risk_dist,
            "unique_articles": len({r.article_id for r in self._records}),
        }
