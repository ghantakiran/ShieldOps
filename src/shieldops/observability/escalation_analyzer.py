"""Alert Escalation Analyzer — analyze alert escalation patterns and outcomes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EscalationLevel(StrEnum):
    L1_INITIAL = "l1_initial"
    L2_ENGINEERING = "l2_engineering"
    L3_SENIOR = "l3_senior"
    L4_MANAGEMENT = "l4_management"
    L5_EXECUTIVE = "l5_executive"


class EscalationReason(StrEnum):
    TIMEOUT = "timeout"
    SEVERITY_INCREASE = "severity_increase"
    CUSTOMER_IMPACT = "customer_impact"
    SLA_RISK = "sla_risk"
    MANUAL = "manual"


class EscalationOutcome(StrEnum):
    RESOLVED = "resolved"
    MITIGATED = "mitigated"
    ESCALATED_FURTHER = "escalated_further"
    FALSE_ALARM = "false_alarm"
    ONGOING = "ongoing"


# --- Models ---


class EscalationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    from_level: EscalationLevel = EscalationLevel.L1_INITIAL
    to_level: EscalationLevel = EscalationLevel.L2_ENGINEERING
    reason: EscalationReason = EscalationReason.TIMEOUT
    outcome: EscalationOutcome = EscalationOutcome.RESOLVED
    team: str = ""
    escalation_time_minutes: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class EscalationPattern(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_type: str = ""
    avg_escalation_time: float = 0.0
    escalation_count: int = 0
    resolution_level: EscalationLevel = EscalationLevel.L1_INITIAL
    created_at: float = Field(default_factory=time.time)


class EscalationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_patterns: int = 0
    escalation_rate_pct: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_reason: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    frequent_escalations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertEscalationAnalyzer:
    """Analyze alert escalation patterns, timing, outcomes, and trends."""

    def __init__(
        self,
        max_records: int = 200000,
        max_escalation_rate_pct: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._max_escalation_rate_pct = max_escalation_rate_pct
        self._records: list[EscalationRecord] = []
        self._patterns: list[EscalationPattern] = []
        logger.info(
            "escalation_analyzer.initialized",
            max_records=max_records,
            max_escalation_rate_pct=max_escalation_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_escalation(
        self,
        alert_id: str,
        from_level: EscalationLevel = EscalationLevel.L1_INITIAL,
        to_level: EscalationLevel = EscalationLevel.L2_ENGINEERING,
        reason: EscalationReason = EscalationReason.TIMEOUT,
        outcome: EscalationOutcome = EscalationOutcome.RESOLVED,
        team: str = "",
        escalation_time_minutes: float = 0.0,
        details: str = "",
    ) -> EscalationRecord:
        record = EscalationRecord(
            alert_id=alert_id,
            from_level=from_level,
            to_level=to_level,
            reason=reason,
            outcome=outcome,
            team=team,
            escalation_time_minutes=escalation_time_minutes,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "escalation_analyzer.recorded",
            record_id=record.id,
            alert_id=alert_id,
            from_level=from_level.value,
            to_level=to_level.value,
        )
        return record

    def get_escalation(self, record_id: str) -> EscalationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_escalations(
        self,
        level: EscalationLevel | None = None,
        reason: EscalationReason | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EscalationRecord]:
        results = list(self._records)
        if level is not None:
            results = [r for r in results if r.to_level == level]
        if reason is not None:
            results = [r for r in results if r.reason == reason]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_pattern(
        self,
        alert_type: str,
        avg_escalation_time: float = 0.0,
        escalation_count: int = 0,
        resolution_level: EscalationLevel = EscalationLevel.L1_INITIAL,
    ) -> EscalationPattern:
        pattern = EscalationPattern(
            alert_type=alert_type,
            avg_escalation_time=avg_escalation_time,
            escalation_count=escalation_count,
            resolution_level=resolution_level,
        )
        self._patterns.append(pattern)
        if len(self._patterns) > self._max_records:
            self._patterns = self._patterns[-self._max_records :]
        logger.info(
            "escalation_analyzer.pattern_added",
            alert_type=alert_type,
            escalation_count=escalation_count,
        )
        return pattern

    # -- domain operations -----------------------------------------------

    def analyze_escalation_by_level(self) -> list[dict[str, Any]]:
        """Analyze escalation counts per target level."""
        level_times: dict[str, list[float]] = {}
        for r in self._records:
            level_times.setdefault(r.to_level.value, []).append(r.escalation_time_minutes)
        results: list[dict[str, Any]] = []
        for level, times in level_times.items():
            results.append(
                {
                    "level": level,
                    "avg_escalation_time": round(sum(times) / len(times), 2),
                    "record_count": len(times),
                }
            )
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    def identify_frequent_escalations(self) -> list[dict[str, Any]]:
        """Find teams with escalation rate exceeding the threshold."""
        team_counts: dict[str, int] = {}
        for r in self._records:
            team_counts[r.team] = team_counts.get(r.team, 0) + 1
        total = len(self._records)
        frequent: list[dict[str, Any]] = []
        for team, count in team_counts.items():
            rate = round(count / total * 100, 2) if total > 0 else 0.0
            if rate > self._max_escalation_rate_pct:
                frequent.append(
                    {
                        "team": team,
                        "escalation_count": count,
                        "escalation_rate_pct": rate,
                    }
                )
        frequent.sort(key=lambda x: x["escalation_rate_pct"], reverse=True)
        return frequent

    def rank_by_escalation_time(self) -> list[dict[str, Any]]:
        """Rank teams by average escalation time."""
        team_times: dict[str, list[float]] = {}
        for r in self._records:
            team_times.setdefault(r.team, []).append(r.escalation_time_minutes)
        results: list[dict[str, Any]] = []
        for team, times in team_times.items():
            results.append(
                {
                    "team": team,
                    "avg_escalation_time": round(sum(times) / len(times), 2),
                    "record_count": len(times),
                }
            )
        results.sort(key=lambda x: x["avg_escalation_time"], reverse=True)
        return results

    def detect_escalation_trends(self) -> list[dict[str, Any]]:
        """Detect escalation trends using split-half comparison."""
        team_records: dict[str, list[float]] = {}
        for r in self._records:
            team_records.setdefault(r.team, []).append(r.escalation_time_minutes)
        results: list[dict[str, Any]] = []
        for team, times in team_records.items():
            if len(times) < 4:
                results.append({"team": team, "trend": "insufficient_data"})
                continue
            mid = len(times) // 2
            first_half_avg = sum(times[:mid]) / mid
            second_half_avg = sum(times[mid:]) / (len(times) - mid)
            delta = second_half_avg - first_half_avg
            if delta > 5.0:
                trend = "increasing"
            elif delta < -5.0:
                trend = "decreasing"
            else:
                trend = "stable"
            results.append(
                {
                    "team": team,
                    "first_half_avg": round(first_half_avg, 2),
                    "second_half_avg": round(second_half_avg, 2),
                    "delta": round(delta, 2),
                    "trend": trend,
                }
            )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> EscalationReport:
        by_level: dict[str, int] = {}
        by_reason: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_level[r.to_level.value] = by_level.get(r.to_level.value, 0) + 1
            by_reason[r.reason.value] = by_reason.get(r.reason.value, 0) + 1
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
        total = len(self._records)
        escalated_further = by_outcome.get(EscalationOutcome.ESCALATED_FURTHER.value, 0)
        rate = round(escalated_further / total * 100, 2) if total > 0 else 0.0
        frequent = self.identify_frequent_escalations()
        frequent_teams = [f["team"] for f in frequent[:10]]
        recs: list[str] = []
        if rate > self._max_escalation_rate_pct:
            recs.append(
                f"Escalation rate {rate}% exceeds {self._max_escalation_rate_pct}% threshold"
            )
        false_alarms = by_outcome.get(EscalationOutcome.FALSE_ALARM.value, 0)
        if false_alarms > 0:
            recs.append(f"{false_alarms} false alarm(s) detected")
        if not recs:
            recs.append("Escalation patterns within acceptable parameters")
        return EscalationReport(
            total_records=total,
            total_patterns=len(self._patterns),
            escalation_rate_pct=rate,
            by_level=by_level,
            by_reason=by_reason,
            by_outcome=by_outcome,
            frequent_escalations=frequent_teams,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._patterns.clear()
        logger.info("escalation_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        reason_dist: dict[str, int] = {}
        for r in self._records:
            key = r.reason.value
            reason_dist[key] = reason_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_patterns": len(self._patterns),
            "max_escalation_rate_pct": self._max_escalation_rate_pct,
            "reason_distribution": reason_dist,
            "unique_alerts": len({r.alert_id for r in self._records}),
        }
