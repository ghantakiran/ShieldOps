"""Alert Routing Optimizer — routing effectiveness, recommendations, fatigue reduction."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RoutingChannel(StrEnum):
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    TEAMS = "teams"


class RoutingEffectiveness(StrEnum):
    OPTIMAL = "optimal"
    ADEQUATE = "adequate"
    SUBOPTIMAL = "suboptimal"
    INEFFECTIVE = "ineffective"


class ActionTaken(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    SUPPRESSED = "suppressed"
    IGNORED = "ignored"
    REASSIGNED = "reassigned"


# --- Models ---


class RoutingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    alert_type: str = ""
    team: str = ""
    channel: RoutingChannel = RoutingChannel.SLACK
    action_taken: ActionTaken = ActionTaken.ACKNOWLEDGED
    response_time_seconds: float = 0.0
    was_rerouted: bool = False
    created_at: float = Field(default_factory=time.time)


class RoutingRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_type: str = ""
    current_channel: RoutingChannel = RoutingChannel.SLACK
    recommended_channel: RoutingChannel = RoutingChannel.PAGERDUTY
    current_team: str = ""
    recommended_team: str = ""
    reason: str = ""
    effectiveness: RoutingEffectiveness = RoutingEffectiveness.ADEQUATE
    created_at: float = Field(default_factory=time.time)


class RoutingAnalysisReport(BaseModel):
    total_routings: int = 0
    reroute_count: int = 0
    reroute_rate: float = 0.0
    ignored_count: int = 0
    ignored_rate: float = 0.0
    channel_effectiveness: dict[str, float] = Field(default_factory=dict)
    team_effectiveness: dict[str, float] = Field(default_factory=dict)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertRoutingOptimizer:
    """Alert routing effectiveness analysis, routing recommendations, fatigue reduction."""

    def __init__(
        self,
        max_records: int = 200000,
        reroute_threshold: float = 0.2,
    ) -> None:
        self._max_records = max_records
        self._reroute_threshold = reroute_threshold
        self._routings: list[RoutingRecord] = []
        self._recommendations: list[RoutingRecommendation] = []
        logger.info(
            "alert_routing.initialized",
            max_records=max_records,
            reroute_threshold=reroute_threshold,
        )

    def record_routing(
        self,
        alert_id: str = "",
        alert_type: str = "",
        team: str = "",
        channel: RoutingChannel = RoutingChannel.SLACK,
        action_taken: ActionTaken = ActionTaken.ACKNOWLEDGED,
        response_time_seconds: float = 0.0,
        was_rerouted: bool = False,
    ) -> RoutingRecord:
        record = RoutingRecord(
            alert_id=alert_id,
            alert_type=alert_type,
            team=team,
            channel=channel,
            action_taken=action_taken,
            response_time_seconds=response_time_seconds,
            was_rerouted=was_rerouted,
        )
        self._routings.append(record)
        if len(self._routings) > self._max_records:
            self._routings = self._routings[-self._max_records :]
        logger.info(
            "alert_routing.recorded",
            routing_id=record.id,
            alert_id=alert_id,
            alert_type=alert_type,
            team=team,
            channel=channel,
            action_taken=action_taken,
        )
        return record

    def get_routing(self, routing_id: str) -> RoutingRecord | None:
        for r in self._routings:
            if r.id == routing_id:
                return r
        return None

    def list_routings(
        self,
        team: str | None = None,
        channel: RoutingChannel | None = None,
        limit: int = 100,
    ) -> list[RoutingRecord]:
        results = list(self._routings)
        if team is not None:
            results = [r for r in results if r.team == team]
        if channel is not None:
            results = [r for r in results if r.channel == channel]
        return results[-limit:]

    def generate_recommendations(self) -> list[RoutingRecommendation]:
        per_type: dict[str, list[RoutingRecord]] = {}
        for r in self._routings:
            per_type.setdefault(r.alert_type, []).append(r)

        new_recommendations: list[RoutingRecommendation] = []
        for alert_type, records in per_type.items():
            if not records:
                continue
            total = len(records)
            rerouted = sum(1 for r in records if r.was_rerouted)
            ignored = sum(1 for r in records if r.action_taken == ActionTaken.IGNORED)
            reroute_rate = rerouted / total
            ignored_rate = ignored / total

            # Determine most common current channel and team
            channel_counts: dict[RoutingChannel, int] = {}
            team_counts: dict[str, int] = {}
            for r in records:
                channel_counts[r.channel] = channel_counts.get(r.channel, 0) + 1
                team_counts[r.team] = team_counts.get(r.team, 0) + 1
            current_channel = max(channel_counts, key=channel_counts.get)  # type: ignore[arg-type]
            current_team = max(team_counts, key=team_counts.get)  # type: ignore[arg-type]

            if reroute_rate > self._reroute_threshold:
                # Recommend a different channel — prefer PagerDuty for high reroute rates
                alt_channel = (
                    RoutingChannel.PAGERDUTY
                    if current_channel != RoutingChannel.PAGERDUTY
                    else RoutingChannel.SLACK
                )
                effectiveness = (
                    RoutingEffectiveness.INEFFECTIVE
                    if reroute_rate > 0.5
                    else RoutingEffectiveness.SUBOPTIMAL
                )
                rec = RoutingRecommendation(
                    alert_type=alert_type,
                    current_channel=current_channel,
                    recommended_channel=alt_channel,
                    current_team=current_team,
                    recommended_team=current_team,
                    reason=(
                        f"High reroute rate ({reroute_rate:.1%}) — "
                        f"switch channel from {current_channel} to {alt_channel}"
                    ),
                    effectiveness=effectiveness,
                )
                new_recommendations.append(rec)
                self._recommendations.append(rec)

            if ignored_rate > 0.5:
                # Recommend a different team
                effectiveness = RoutingEffectiveness.INEFFECTIVE
                rec = RoutingRecommendation(
                    alert_type=alert_type,
                    current_channel=current_channel,
                    recommended_channel=current_channel,
                    current_team=current_team,
                    recommended_team=f"{current_team}-escalation",
                    reason=(
                        f"High ignored rate ({ignored_rate:.1%}) — "
                        f"reassign from {current_team} to escalation team"
                    ),
                    effectiveness=effectiveness,
                )
                new_recommendations.append(rec)
                self._recommendations.append(rec)

        logger.info(
            "alert_routing.recommendations_generated",
            count=len(new_recommendations),
        )
        return new_recommendations

    def analyze_team_effectiveness(
        self,
        team: str | None = None,
    ) -> dict[str, Any]:
        per_team: dict[str, list[RoutingRecord]] = {}
        for r in self._routings:
            if team is not None and r.team != team:
                continue
            per_team.setdefault(r.team, []).append(r)

        result: dict[str, Any] = {}
        for team_name, records in per_team.items():
            total = len(records)
            resolved = sum(1 for r in records if r.action_taken == ActionTaken.RESOLVED)
            rerouted = sum(1 for r in records if r.was_rerouted)
            total_response_time = sum(r.response_time_seconds for r in records)
            result[team_name] = {
                "total_routings": total,
                "avg_response_time": round(total_response_time / total, 2) if total > 0 else 0.0,
                "resolve_rate": round(resolved / total, 3) if total > 0 else 0.0,
                "reroute_rate": round(rerouted / total, 3) if total > 0 else 0.0,
            }
        return result

    def detect_reroute_patterns(self) -> list[dict[str, Any]]:
        per_type: dict[str, list[RoutingRecord]] = {}
        for r in self._routings:
            per_type.setdefault(r.alert_type, []).append(r)

        patterns: list[dict[str, Any]] = []
        for alert_type, records in per_type.items():
            total = len(records)
            rerouted = sum(1 for r in records if r.was_rerouted)
            rate = rerouted / total if total > 0 else 0.0
            if rate > self._reroute_threshold:
                patterns.append(
                    {
                        "alert_type": alert_type,
                        "total_routings": total,
                        "rerouted_count": rerouted,
                        "reroute_rate": round(rate, 3),
                    }
                )
        patterns.sort(key=lambda p: p["reroute_rate"], reverse=True)
        logger.info("alert_routing.reroute_patterns_detected", count=len(patterns))
        return patterns

    def compute_channel_effectiveness(self) -> dict[str, float]:
        per_channel: dict[str, dict[str, int]] = {}
        for r in self._routings:
            ch = r.channel.value
            if ch not in per_channel:
                per_channel[ch] = {"total": 0, "effective": 0}
            per_channel[ch]["total"] += 1
            if r.action_taken in (ActionTaken.RESOLVED, ActionTaken.ACKNOWLEDGED):
                per_channel[ch]["effective"] += 1

        result: dict[str, float] = {}
        for ch, stats in per_channel.items():
            result[ch] = (
                round(stats["effective"] / stats["total"], 3) if stats["total"] > 0 else 0.0
            )
        return result

    def identify_ignored_alerts(self, limit: int = 50) -> list[RoutingRecord]:
        ignored = [r for r in self._routings if r.action_taken == ActionTaken.IGNORED]
        return ignored[-limit:]

    def generate_analysis_report(self) -> RoutingAnalysisReport:
        total = len(self._routings)
        rerouted = sum(1 for r in self._routings if r.was_rerouted)
        ignored = sum(1 for r in self._routings if r.action_taken == ActionTaken.IGNORED)

        channel_eff = self.compute_channel_effectiveness()
        team_eff_raw = self.analyze_team_effectiveness()
        team_eff: dict[str, float] = {t: stats["resolve_rate"] for t, stats in team_eff_raw.items()}

        recommendations = self.generate_recommendations()
        rec_dicts = [
            {
                "alert_type": rec.alert_type,
                "current_channel": rec.current_channel.value,
                "recommended_channel": rec.recommended_channel.value,
                "current_team": rec.current_team,
                "recommended_team": rec.recommended_team,
                "reason": rec.reason,
                "effectiveness": rec.effectiveness.value,
            }
            for rec in recommendations
        ]

        report = RoutingAnalysisReport(
            total_routings=total,
            reroute_count=rerouted,
            reroute_rate=round(rerouted / total, 3) if total > 0 else 0.0,
            ignored_count=ignored,
            ignored_rate=round(ignored / total, 3) if total > 0 else 0.0,
            channel_effectiveness=channel_eff,
            team_effectiveness=team_eff,
            recommendations=rec_dicts,
        )
        logger.info(
            "alert_routing.report_generated",
            total_routings=total,
            reroute_rate=report.reroute_rate,
            ignored_rate=report.ignored_rate,
        )
        return report

    def clear_data(self) -> None:
        self._routings.clear()
        self._recommendations.clear()
        logger.info("alert_routing.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        alert_types = {r.alert_type for r in self._routings}
        teams = {r.team for r in self._routings}
        return {
            "total_routings": len(self._routings),
            "total_recommendations": len(self._recommendations),
            "unique_alert_types": len(alert_types),
            "unique_teams": len(teams),
            "alert_types": sorted(alert_types),
            "teams": sorted(teams),
        }
