"""Alert Priority Optimizer — optimize alert priority from response patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PriorityLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class OptimizationAction(StrEnum):
    UPGRADE = "upgrade"
    MAINTAIN = "maintain"
    DOWNGRADE = "downgrade"
    SUPPRESS = "suppress"
    REVIEW = "review"


class ResponsePattern(StrEnum):
    IMMEDIATE = "immediate"
    DELAYED = "delayed"
    IGNORED = "ignored"
    ESCALATED = "escalated"
    AUTO_RESOLVED = "auto_resolved"


# --- Models ---


class PriorityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_type: str = ""
    current_priority: PriorityLevel = PriorityLevel.INFORMATIONAL
    suggested_priority: PriorityLevel = PriorityLevel.INFORMATIONAL
    action: OptimizationAction = OptimizationAction.MAINTAIN
    response_pattern: ResponsePattern = ResponsePattern.IMMEDIATE
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PriorityRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_pattern: str = ""
    priority_level: PriorityLevel = PriorityLevel.INFORMATIONAL
    action: OptimizationAction = OptimizationAction.MAINTAIN
    confidence_pct: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertPriorityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    optimization_count: int = 0
    misalignment_rate_pct: float = 0.0
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    by_response: dict[str, int] = Field(default_factory=dict)
    misaligned_alerts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertPriorityOptimizer:
    """Optimize alert priority based on historical response patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        max_misalignment_pct: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._max_misalignment_pct = max_misalignment_pct
        self._records: list[PriorityRecord] = []
        self._rules: list[PriorityRule] = []
        logger.info(
            "alert_priority.initialized",
            max_records=max_records,
            max_misalignment_pct=max_misalignment_pct,
        )

    # -- record / get / list -----------------------------------------------

    def record_priority(
        self,
        alert_type: str,
        current_priority: PriorityLevel = (PriorityLevel.INFORMATIONAL),
        suggested_priority: PriorityLevel = (PriorityLevel.INFORMATIONAL),
        action: OptimizationAction = (OptimizationAction.MAINTAIN),
        response_pattern: ResponsePattern = (ResponsePattern.IMMEDIATE),
        team: str = "",
        details: str = "",
    ) -> PriorityRecord:
        record = PriorityRecord(
            alert_type=alert_type,
            current_priority=current_priority,
            suggested_priority=suggested_priority,
            action=action,
            response_pattern=response_pattern,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_priority.priority_recorded",
            record_id=record.id,
            alert_type=alert_type,
            current_priority=current_priority.value,
            action=action.value,
        )
        return record

    def get_priority(self, record_id: str) -> PriorityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_priorities(
        self,
        priority: PriorityLevel | None = None,
        action: OptimizationAction | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PriorityRecord]:
        results = list(self._records)
        if priority is not None:
            results = [r for r in results if r.current_priority == priority]
        if action is not None:
            results = [r for r in results if r.action == action]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        alert_pattern: str,
        priority_level: PriorityLevel = (PriorityLevel.INFORMATIONAL),
        action: OptimizationAction = (OptimizationAction.MAINTAIN),
        confidence_pct: float = 0.0,
        reason: str = "",
    ) -> PriorityRule:
        rule = PriorityRule(
            alert_pattern=alert_pattern,
            priority_level=priority_level,
            action=action,
            confidence_pct=confidence_pct,
            reason=reason,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "alert_priority.rule_added",
            alert_pattern=alert_pattern,
            priority_level=priority_level.value,
            confidence_pct=confidence_pct,
        )
        return rule

    # -- domain operations -------------------------------------------------

    def analyze_priority_distribution(
        self,
    ) -> dict[str, Any]:
        """Group by current_priority; count and avg action score."""
        action_map = {
            OptimizationAction.UPGRADE: 5,
            OptimizationAction.MAINTAIN: 4,
            OptimizationAction.DOWNGRADE: 3,
            OptimizationAction.SUPPRESS: 2,
            OptimizationAction.REVIEW: 1,
        }
        prio_data: dict[str, list[int]] = {}
        for r in self._records:
            key = r.current_priority.value
            prio_data.setdefault(key, []).append(action_map.get(r.action, 1))
        result: dict[str, Any] = {}
        for prio, scores in prio_data.items():
            result[prio] = {
                "count": len(scores),
                "avg_action_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_misaligned_priorities(
        self,
    ) -> list[dict[str, Any]]:
        """Return records where current != suggested."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.current_priority != r.suggested_priority:
                results.append(
                    {
                        "record_id": r.id,
                        "alert_type": r.alert_type,
                        "current_priority": (r.current_priority.value),
                        "suggested_priority": (r.suggested_priority.value),
                        "action": r.action.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_misalignment(
        self,
    ) -> list[dict[str, Any]]:
        """Group by alert_type, count misalignments, sort desc."""
        type_counts: dict[str, int] = {}
        for r in self._records:
            if r.current_priority != r.suggested_priority:
                type_counts[r.alert_type] = type_counts.get(r.alert_type, 0) + 1
        results: list[dict[str, Any]] = []
        for atype, count in type_counts.items():
            results.append(
                {
                    "alert_type": atype,
                    "misalignment_count": count,
                }
            )
        results.sort(
            key=lambda x: x["misalignment_count"],
            reverse=True,
        )
        return results

    def detect_priority_trends(self) -> dict[str, Any]:
        """Split-half on confidence_pct; delta threshold 5.0."""
        if len(self._rules) < 2:
            return {
                "trend": "insufficient_data",
                "delta": 0.0,
            }
        vals = [ru.confidence_pct for ru in self._rules]
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

    # -- report / stats ----------------------------------------------------

    def generate_report(self) -> AlertPriorityReport:
        by_priority: dict[str, int] = {}
        by_action: dict[str, int] = {}
        by_response: dict[str, int] = {}
        for r in self._records:
            by_priority[r.current_priority.value] = by_priority.get(r.current_priority.value, 0) + 1
            by_action[r.action.value] = by_action.get(r.action.value, 0) + 1
            by_response[r.response_pattern.value] = by_response.get(r.response_pattern.value, 0) + 1
        misaligned = self.identify_misaligned_priorities()
        misalignment_count = len(misaligned)
        misalignment_rate = (
            round(
                misalignment_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        optimization_count = sum(
            1 for r in self._records if r.action != OptimizationAction.MAINTAIN
        )
        misaligned_alerts = [m["alert_type"] for m in misaligned[:10]]
        recs: list[str] = []
        if misalignment_rate > self._max_misalignment_pct:
            recs.append(
                f"Misalignment rate {misalignment_rate}%"
                f" exceeds threshold"
                f" ({self._max_misalignment_pct}%)"
            )
        if misalignment_count > 0:
            recs.append(f"{misalignment_count} misaligned priority(ies) — review alert config")
        if not recs:
            recs.append("Alert priority levels are healthy")
        return AlertPriorityReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            optimization_count=optimization_count,
            misalignment_rate_pct=misalignment_rate,
            by_priority=by_priority,
            by_action=by_action,
            by_response=by_response,
            misaligned_alerts=misaligned_alerts,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("alert_priority.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        prio_dist: dict[str, int] = {}
        for r in self._records:
            key = r.current_priority.value
            prio_dist[key] = prio_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "max_misalignment_pct": (self._max_misalignment_pct),
            "priority_distribution": prio_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_alert_types": len({r.alert_type for r in self._records}),
        }
