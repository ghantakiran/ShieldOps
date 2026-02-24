"""Alert Fatigue Scorer — measure alert fatigue per team/service."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FatigueLevel(StrEnum):
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class AlertActionability(StrEnum):
    ACTIONABLE = "actionable"
    INFORMATIONAL = "informational"
    DUPLICATE = "duplicate"
    FALSE_POSITIVE = "false_positive"
    STALE = "stale"


class ResponderEngagement(StrEnum):
    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    IGNORED = "ignored"
    BULK_DISMISSED = "bulk_dismissed"
    AUTO_RESOLVED = "auto_resolved"


# --- Models ---


class AlertFatigueRecord(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    team: str = ""
    service_name: str = ""
    alert_count: int = 0
    actionable_count: int = 0
    ignored_count: int = 0
    fatigue_level: FatigueLevel = FatigueLevel.MINIMAL
    engagement_rate: float = 0.0
    window_start: float = 0.0
    window_end: float = 0.0
    created_at: float = Field(default_factory=time.time)


class FatigueScore(BaseModel):
    team: str = ""
    service_name: str = ""
    fatigue_level: FatigueLevel = FatigueLevel.MINIMAL
    score: float = 0.0
    alert_volume: int = 0
    actionability_pct: float = 0.0
    engagement_pct: float = 0.0
    trend: str = "stable"
    created_at: float = Field(default_factory=time.time)


class FatigueReport(BaseModel):
    total_teams: int = 0
    total_alerts_analyzed: int = 0
    avg_fatigue_score: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_actionability: dict[str, int] = Field(
        default_factory=dict,
    )
    high_fatigue_teams: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Scorer ---


class AlertFatigueScorer:
    """Measure alert fatigue per team/service."""

    def __init__(
        self,
        max_records: int = 500000,
        fatigue_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._fatigue_threshold = fatigue_threshold
        self._items: list[AlertFatigueRecord] = []
        self._scores: dict[str, FatigueScore] = {}
        logger.info(
            "alert_fatigue.initialized",
            max_records=max_records,
            fatigue_threshold=fatigue_threshold,
        )

    # -- record --

    def record_alert(
        self,
        team: str,
        service_name: str = "",
        alert_count: int = 1,
        actionable_count: int = 0,
        ignored_count: int = 0,
        engagement_rate: float = 0.0,
        **kw: Any,
    ) -> AlertFatigueRecord:
        """Record an alert fatigue observation."""
        fatigue_level = self._compute_level(
            alert_count,
            actionable_count,
            ignored_count,
        )
        record = AlertFatigueRecord(
            team=team,
            service_name=service_name,
            alert_count=alert_count,
            actionable_count=actionable_count,
            ignored_count=ignored_count,
            fatigue_level=fatigue_level,
            engagement_rate=engagement_rate,
            **kw,
        )
        self._items.append(record)
        if len(self._items) > self._max_records:
            self._items = self._items[-self._max_records :]
        logger.info(
            "alert_fatigue.recorded",
            record_id=record.id,
            team=team,
            fatigue_level=fatigue_level,
        )
        return record

    # -- get / list --

    def get_record(self, record_id: str) -> AlertFatigueRecord | None:
        """Get a single record by ID."""
        for item in self._items:
            if item.id == record_id:
                return item
        return None

    def list_records(
        self,
        team: str | None = None,
        service_name: str | None = None,
        limit: int = 50,
    ) -> list[AlertFatigueRecord]:
        """List records with optional filters."""
        results = list(self._items)
        if team is not None:
            results = [r for r in results if r.team == team]
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        return results[-limit:]

    # -- domain operations --

    def calculate_fatigue_score(
        self,
        team: str,
    ) -> FatigueScore:
        """Calculate fatigue score for a team."""
        records = [r for r in self._items if r.team == team]
        if not records:
            return FatigueScore(team=team)
        total_alerts = sum(r.alert_count for r in records)
        total_actionable = sum(r.actionable_count for r in records)
        total_ignored = sum(r.ignored_count for r in records)
        actionability_pct = round(total_actionable / total_alerts * 100, 2) if total_alerts else 0.0
        engagement_pct = (
            round(
                (total_alerts - total_ignored) / total_alerts * 100,
                2,
            )
            if total_alerts
            else 0.0
        )
        # Score: high ignored + low actionability = high fatigue
        raw = 0.0
        if total_alerts:
            ignored_ratio = total_ignored / total_alerts
            raw = round(ignored_ratio * 100, 2)
        level = self._score_to_level(raw)
        # Trend detection
        trend = self._detect_trend(records)
        score = FatigueScore(
            team=team,
            service_name=records[-1].service_name,
            fatigue_level=level,
            score=raw,
            alert_volume=total_alerts,
            actionability_pct=actionability_pct,
            engagement_pct=engagement_pct,
            trend=trend,
        )
        self._scores[team] = score
        logger.info(
            "alert_fatigue.score_calculated",
            team=team,
            score=raw,
            level=level,
        )
        return score

    def detect_fatigue_trends(self) -> list[dict[str, Any]]:
        """Detect fatigue trends across all teams."""
        teams = {r.team for r in self._items}
        trends: list[dict[str, Any]] = []
        for team in sorted(teams):
            records = [r for r in self._items if r.team == team]
            trend = self._detect_trend(records)
            trends.append(
                {
                    "team": team,
                    "trend": trend,
                    "record_count": len(records),
                }
            )
        return trends

    def identify_noisy_alerts(self) -> list[dict[str, Any]]:
        """Identify services with high alert-to-action ratio."""
        by_svc: dict[str, list[AlertFatigueRecord]] = {}
        for r in self._items:
            by_svc.setdefault(r.service_name, []).append(r)
        noisy: list[dict[str, Any]] = []
        for svc, records in sorted(by_svc.items()):
            total = sum(r.alert_count for r in records)
            actionable = sum(r.actionable_count for r in records)
            ratio = round(actionable / total * 100, 2) if total else 0.0
            if ratio < 50.0:
                noisy.append(
                    {
                        "service_name": svc,
                        "total_alerts": total,
                        "actionable_count": actionable,
                        "actionability_pct": ratio,
                    }
                )
        noisy.sort(key=lambda x: x["actionability_pct"])
        return noisy

    def rank_teams_by_fatigue(
        self,
    ) -> list[FatigueScore]:
        """Rank teams by fatigue score descending."""
        teams = {r.team for r in self._items}
        scores: list[FatigueScore] = []
        for team in teams:
            score = self.calculate_fatigue_score(team)
            scores.append(score)
        scores.sort(key=lambda s: s.score, reverse=True)
        return scores

    def suggest_alert_tuning(
        self,
    ) -> list[dict[str, Any]]:
        """Suggest tuning actions based on fatigue data."""
        suggestions: list[dict[str, Any]] = []
        noisy = self.identify_noisy_alerts()
        for item in noisy:
            suggestions.append(
                {
                    "service_name": item["service_name"],
                    "action": "reduce_alert_volume",
                    "reason": (f"Only {item['actionability_pct']}% of alerts are actionable"),
                }
            )
        ranked = self.rank_teams_by_fatigue()
        for score in ranked:
            if score.score >= self._fatigue_threshold:
                suggestions.append(
                    {
                        "team": score.team,
                        "action": "redistribute_oncall",
                        "reason": (f"Fatigue score {score.score} exceeds threshold"),
                    }
                )
        return suggestions

    # -- report --

    def generate_fatigue_report(self) -> FatigueReport:
        """Generate a comprehensive fatigue report."""
        teams = {r.team for r in self._items}
        total_alerts = sum(r.alert_count for r in self._items)
        scores = self.rank_teams_by_fatigue()
        avg_score = (
            round(
                sum(s.score for s in scores) / len(scores),
                2,
            )
            if scores
            else 0.0
        )
        by_level: dict[str, int] = {}
        for r in self._items:
            key = r.fatigue_level.value
            by_level[key] = by_level.get(key, 0) + 1
        by_actionability: dict[str, int] = {}
        for r in self._items:
            key = "actionable" if r.actionable_count > 0 else "non_actionable"
            by_actionability[key] = by_actionability.get(key, 0) + 1
        high_fatigue = [s.team for s in scores if s.score >= self._fatigue_threshold]
        recs = self._build_recommendations(
            scores,
            total_alerts,
        )
        return FatigueReport(
            total_teams=len(teams),
            total_alerts_analyzed=total_alerts,
            avg_fatigue_score=avg_score,
            by_level=by_level,
            by_actionability=by_actionability,
            high_fatigue_teams=high_fatigue,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all records. Returns count cleared."""
        count = len(self._items)
        self._items.clear()
        self._scores.clear()
        logger.info("alert_fatigue.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        teams = {r.team for r in self._items}
        level_dist: dict[str, int] = {}
        for r in self._items:
            key = r.fatigue_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._items),
            "total_teams": len(teams),
            "fatigue_threshold": self._fatigue_threshold,
            "level_distribution": level_dist,
        }

    # -- internal helpers --

    def _compute_level(
        self,
        alert_count: int,
        actionable_count: int,
        ignored_count: int,
    ) -> FatigueLevel:
        if alert_count == 0:
            return FatigueLevel.MINIMAL
        ignored_ratio = ignored_count / alert_count * 100
        if ignored_ratio >= 80:
            return FatigueLevel.CRITICAL
        if ignored_ratio >= 60:
            return FatigueLevel.HIGH
        if ignored_ratio >= 40:
            return FatigueLevel.MODERATE
        if ignored_ratio >= 20:
            return FatigueLevel.LOW
        return FatigueLevel.MINIMAL

    def _score_to_level(self, score: float) -> FatigueLevel:
        if score >= 80:
            return FatigueLevel.CRITICAL
        if score >= 60:
            return FatigueLevel.HIGH
        if score >= 40:
            return FatigueLevel.MODERATE
        if score >= 20:
            return FatigueLevel.LOW
        return FatigueLevel.MINIMAL

    def _detect_trend(
        self,
        records: list[AlertFatigueRecord],
    ) -> str:
        if len(records) < 2:
            return "stable"
        mid = len(records) // 2
        first_half = records[:mid]
        second_half = records[mid:]
        avg_first = sum(r.ignored_count for r in first_half) / len(first_half) if first_half else 0
        avg_second = (
            sum(r.ignored_count for r in second_half) / len(second_half) if second_half else 0
        )
        if avg_second > avg_first * 1.2:
            return "worsening"
        if avg_second < avg_first * 0.8:
            return "improving"
        return "stable"

    def _build_recommendations(
        self,
        scores: list[FatigueScore],
        total_alerts: int,
    ) -> list[str]:
        recs: list[str] = []
        high = [s for s in scores if s.score >= self._fatigue_threshold]
        if high:
            recs.append(f"{len(high)} team(s) above fatigue threshold - review alert policies")
        if total_alerts > 1000:
            recs.append("High alert volume detected - consider alert consolidation")
        if not recs:
            recs.append("Alert fatigue levels within acceptable range")
        return recs
