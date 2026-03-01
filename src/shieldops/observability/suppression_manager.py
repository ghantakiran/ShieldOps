"""Alert Suppression Manager — track suppression records, rules, and effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SuppressionType(StrEnum):
    MAINTENANCE = "maintenance"
    KNOWN_ISSUE = "known_issue"
    FALSE_POSITIVE = "false_positive"
    TRANSIENT = "transient"
    PLANNED_CHANGE = "planned_change"


class SuppressionScope(StrEnum):
    SERVICE = "service"
    TEAM = "team"
    ALERT_TYPE = "alert_type"
    ENVIRONMENT = "environment"
    GLOBAL = "global"


class SuppressionStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    EXTENDED = "extended"
    PENDING = "pending"


# --- Models ---


class SuppressionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_type: str = ""
    suppression_type: SuppressionType = SuppressionType.MAINTENANCE
    scope: SuppressionScope = SuppressionScope.SERVICE
    status: SuppressionStatus = SuppressionStatus.PENDING
    suppressed_count: int = 0
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class SuppressionRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_pattern: str = ""
    suppression_type: SuppressionType = SuppressionType.MAINTENANCE
    scope: SuppressionScope = SuppressionScope.SERVICE
    duration_minutes: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertSuppressionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    active_suppressions: int = 0
    suppression_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    over_suppressed: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertSuppressionManager:
    """Manage alert suppression records, rules, and effectiveness analysis."""

    def __init__(
        self,
        max_records: int = 200000,
        max_suppression_rate_pct: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._max_suppression_rate_pct = max_suppression_rate_pct
        self._records: list[SuppressionRecord] = []
        self._rules: list[SuppressionRule] = []
        logger.info(
            "suppression_manager.initialized",
            max_records=max_records,
            max_suppression_rate_pct=max_suppression_rate_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_suppression(
        self,
        alert_type: str = "",
        suppression_type: SuppressionType = SuppressionType.MAINTENANCE,
        scope: SuppressionScope = SuppressionScope.SERVICE,
        status: SuppressionStatus = SuppressionStatus.PENDING,
        suppressed_count: int = 0,
        team: str = "",
        details: str = "",
    ) -> SuppressionRecord:
        record = SuppressionRecord(
            alert_type=alert_type,
            suppression_type=suppression_type,
            scope=scope,
            status=status,
            suppressed_count=suppressed_count,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "suppression_manager.suppression_recorded",
            record_id=record.id,
            alert_type=alert_type,
            suppression_type=suppression_type.value,
        )
        return record

    def get_suppression(self, record_id: str) -> SuppressionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_suppressions(
        self,
        suppression_type: SuppressionType | None = None,
        scope: SuppressionScope | None = None,
        status: SuppressionStatus | None = None,
        limit: int = 50,
    ) -> list[SuppressionRecord]:
        results = list(self._records)
        if suppression_type is not None:
            results = [r for r in results if r.suppression_type == suppression_type]
        if scope is not None:
            results = [r for r in results if r.scope == scope]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    def add_rule(
        self,
        alert_pattern: str = "",
        suppression_type: SuppressionType = SuppressionType.MAINTENANCE,
        scope: SuppressionScope = SuppressionScope.SERVICE,
        duration_minutes: float = 0.0,
        reason: str = "",
    ) -> SuppressionRule:
        rule = SuppressionRule(
            alert_pattern=alert_pattern,
            suppression_type=suppression_type,
            scope=scope,
            duration_minutes=duration_minutes,
            reason=reason,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "suppression_manager.rule_added",
            rule_id=rule.id,
            alert_pattern=alert_pattern,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_suppression_effectiveness(self) -> dict[str, Any]:
        """Group records by suppression_type; return count and avg suppressed_count."""
        type_data: dict[str, list[int]] = {}
        for r in self._records:
            key = r.suppression_type.value
            type_data.setdefault(key, []).append(r.suppressed_count)
        result: dict[str, Any] = {}
        for stype, counts in type_data.items():
            result[stype] = {
                "count": len(counts),
                "avg_suppressed_count": round(sum(counts) / len(counts), 2),
            }
        return result

    def identify_over_suppressed(self) -> list[dict[str, Any]]:
        """Return teams whose avg suppressed_count exceeds threshold."""
        team_counts: dict[str, list[int]] = {}
        for r in self._records:
            if r.team:
                team_counts.setdefault(r.team, []).append(r.suppressed_count)
        results: list[dict[str, Any]] = []
        for team, counts in team_counts.items():
            avg = sum(counts) / len(counts)
            if avg > self._max_suppression_rate_pct:
                results.append(
                    {
                        "team": team,
                        "avg_suppressed_count": round(avg, 2),
                        "record_count": len(counts),
                    }
                )
        results.sort(key=lambda x: x["avg_suppressed_count"], reverse=True)
        return results

    def rank_by_suppressed_count(self) -> list[dict[str, Any]]:
        """Group by team, compute total suppressed_count, sort descending."""
        team_totals: dict[str, int] = {}
        for r in self._records:
            if r.team:
                team_totals[r.team] = team_totals.get(r.team, 0) + r.suppressed_count
        results: list[dict[str, Any]] = []
        for team, total in team_totals.items():
            results.append({"team": team, "total_suppressed": total})
        results.sort(key=lambda x: x["total_suppressed"], reverse=True)
        return results

    def detect_suppression_trends(self) -> dict[str, Any]:
        """Split-half comparison on suppressed_count; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [r.suppressed_count for r in self._records]
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

    def generate_report(self) -> AlertSuppressionReport:
        by_type: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.suppression_type.value] = by_type.get(r.suppression_type.value, 0) + 1
            by_scope[r.scope.value] = by_scope.get(r.scope.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        active_suppressions = sum(1 for r in self._records if r.status == SuppressionStatus.ACTIVE)
        total = len(self._records)
        suppression_rate = round(active_suppressions / total * 100, 2) if total else 0.0
        over = self.identify_over_suppressed()
        over_teams = [o["team"] for o in over]
        recs: list[str] = []
        if over:
            recs.append(f"{len(over)} team(s) over-suppressed — review suppression policies")
        if suppression_rate > self._max_suppression_rate_pct and self._max_suppression_rate_pct > 0:
            recs.append(
                f"Suppression rate {suppression_rate}% exceeds threshold "
                f"({self._max_suppression_rate_pct}%)"
            )
        if not recs:
            recs.append("Suppression levels are acceptable")
        return AlertSuppressionReport(
            total_records=total,
            total_rules=len(self._rules),
            active_suppressions=active_suppressions,
            suppression_rate_pct=suppression_rate,
            by_type=by_type,
            by_scope=by_scope,
            by_status=by_status,
            over_suppressed=over_teams,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("suppression_manager.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.suppression_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "max_suppression_rate_pct": self._max_suppression_rate_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records if r.team}),
            "unique_alert_types": len({r.alert_type for r in self._records if r.alert_type}),
        }
