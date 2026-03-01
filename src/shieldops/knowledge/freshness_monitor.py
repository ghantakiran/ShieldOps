"""Knowledge Freshness Monitor — track and analyze knowledge content freshness."""

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
    EXPIRED = "expired"


class ContentType(StrEnum):
    RUNBOOK = "runbook"
    DOCUMENTATION = "documentation"
    PLAYBOOK = "playbook"
    FAQ = "faq"
    ARCHITECTURE_DIAGRAM = "architecture_diagram"


class UpdatePriority(StrEnum):
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


# --- Models ---


class FreshnessRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    article_id: str = ""
    freshness: FreshnessLevel = FreshnessLevel.CURRENT
    content_type: ContentType = ContentType.DOCUMENTATION
    priority: UpdatePriority = UpdatePriority.MEDIUM
    age_days: float = 0.0
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class FreshnessAlert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    record_id: str = ""
    alert_reason: str = ""
    priority: UpdatePriority = UpdatePriority.MEDIUM
    recommended_action: str = ""
    created_at: float = Field(default_factory=time.time)


class KnowledgeFreshnessReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_alerts: int = 0
    stale_count: int = 0
    expired_count: int = 0
    avg_age_days: float = 0.0
    by_freshness: dict[str, int] = Field(default_factory=dict)
    by_content_type: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    most_stale: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class KnowledgeFreshnessMonitor:
    """Track and analyze knowledge content freshness."""

    def __init__(
        self,
        max_records: int = 200000,
        max_stale_days: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._max_stale_days = max_stale_days
        self._records: list[FreshnessRecord] = []
        self._alerts: list[FreshnessAlert] = []
        logger.info(
            "freshness_monitor.initialized",
            max_records=max_records,
            max_stale_days=max_stale_days,
        )

    # -- record / get / list ---------------------------------------------

    def record_freshness(
        self,
        article_id: str,
        freshness: FreshnessLevel = FreshnessLevel.CURRENT,
        content_type: ContentType = ContentType.DOCUMENTATION,
        priority: UpdatePriority = UpdatePriority.MEDIUM,
        age_days: float = 0.0,
        team: str = "",
        details: str = "",
    ) -> FreshnessRecord:
        record = FreshnessRecord(
            article_id=article_id,
            freshness=freshness,
            content_type=content_type,
            priority=priority,
            age_days=age_days,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "freshness_monitor.recorded",
            record_id=record.id,
            article_id=article_id,
            freshness=freshness.value,
        )
        return record

    def get_freshness(self, record_id: str) -> FreshnessRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_freshness_records(
        self,
        freshness: FreshnessLevel | None = None,
        content_type: ContentType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FreshnessRecord]:
        results = list(self._records)
        if freshness is not None:
            results = [r for r in results if r.freshness == freshness]
        if content_type is not None:
            results = [r for r in results if r.content_type == content_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_alert(
        self,
        record_id: str,
        alert_reason: str = "",
        priority: UpdatePriority = UpdatePriority.MEDIUM,
        recommended_action: str = "",
    ) -> FreshnessAlert:
        alert = FreshnessAlert(
            record_id=record_id,
            alert_reason=alert_reason,
            priority=priority,
            recommended_action=recommended_action,
        )
        self._alerts.append(alert)
        if len(self._alerts) > self._max_records:
            self._alerts = self._alerts[-self._max_records :]
        logger.info(
            "freshness_monitor.alert_added",
            alert_id=alert.id,
            record_id=record_id,
            priority=priority.value,
        )
        return alert

    # -- domain operations -----------------------------------------------

    def analyze_freshness_distribution(self) -> dict[str, Any]:
        """Group records by content_type, compute avg age_days and count."""
        groups: dict[str, list[float]] = {}
        for r in self._records:
            groups.setdefault(r.content_type.value, []).append(r.age_days)
        result: dict[str, Any] = {}
        for ct, ages in groups.items():
            result[ct] = {
                "count": len(ages),
                "avg_age_days": round(sum(ages) / len(ages), 2),
            }
        return result

    def identify_stale_content(self) -> list[dict[str, Any]]:
        """Find records with age_days exceeding max_stale_days."""
        stale = [r for r in self._records if r.age_days > self._max_stale_days]
        return [
            {
                "record_id": r.id,
                "article_id": r.article_id,
                "age_days": r.age_days,
                "content_type": r.content_type.value,
                "team": r.team,
            }
            for r in stale
        ]

    def rank_by_age(self) -> list[dict[str, Any]]:
        """Group records by team, compute avg age_days, sort descending."""
        team_ages: dict[str, list[float]] = {}
        for r in self._records:
            team_ages.setdefault(r.team, []).append(r.age_days)
        results: list[dict[str, Any]] = []
        for team, ages in team_ages.items():
            results.append({"team": team, "avg_age_days": round(sum(ages) / len(ages), 2)})
        results.sort(key=lambda x: x["avg_age_days"], reverse=True)
        return results

    def detect_freshness_trends(self) -> dict[str, Any]:
        """Split records in half and compute delta in avg age_days; threshold 5.0."""
        if len(self._records) < 2:
            return {"status": "insufficient_data"}
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]
        avg_first = sum(r.age_days for r in first_half) / len(first_half)
        avg_second = sum(r.age_days for r in second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        trend = "worsening" if delta > 5.0 else ("improving" if delta < -5.0 else "stable")
        return {
            "avg_age_first_half": round(avg_first, 2),
            "avg_age_second_half": round(avg_second, 2),
            "delta": delta,
            "trend": trend,
        }

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> KnowledgeFreshnessReport:
        by_freshness: dict[str, int] = {}
        by_content_type: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        for r in self._records:
            by_freshness[r.freshness.value] = by_freshness.get(r.freshness.value, 0) + 1
            by_content_type[r.content_type.value] = by_content_type.get(r.content_type.value, 0) + 1
            by_priority[r.priority.value] = by_priority.get(r.priority.value, 0) + 1
        stale_count = sum(1 for r in self._records if r.freshness in (FreshnessLevel.STALE,))
        expired_count = sum(1 for r in self._records if r.freshness == FreshnessLevel.EXPIRED)
        avg_age = (
            round(sum(r.age_days for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        sorted_stale = sorted(self._records, key=lambda r: r.age_days, reverse=True)
        most_stale = [r.article_id for r in sorted_stale[:5]]
        recs: list[str] = []
        if stale_count > 0:
            recs.append(f"{stale_count} article(s) are stale and require updates")
        if expired_count > 0:
            recs.append(f"{expired_count} article(s) have expired — immediate action needed")
        over_threshold = sum(1 for r in self._records if r.age_days > self._max_stale_days)
        if over_threshold > 0:
            recs.append(
                f"{over_threshold} article(s) exceed the {self._max_stale_days}-day threshold"
            )
        if not recs:
            recs.append("Knowledge freshness is within acceptable limits")
        return KnowledgeFreshnessReport(
            total_records=len(self._records),
            total_alerts=len(self._alerts),
            stale_count=stale_count,
            expired_count=expired_count,
            avg_age_days=avg_age,
            by_freshness=by_freshness,
            by_content_type=by_content_type,
            by_priority=by_priority,
            most_stale=most_stale,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._alerts.clear()
        logger.info("freshness_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        freshness_dist: dict[str, int] = {}
        for r in self._records:
            key = r.freshness.value
            freshness_dist[key] = freshness_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_alerts": len(self._alerts),
            "max_stale_days": self._max_stale_days,
            "freshness_distribution": freshness_dist,
            "unique_teams": len({r.team for r in self._records}),
        }
