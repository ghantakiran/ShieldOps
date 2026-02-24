"""Alert Correlation Rule Engine — define and evaluate correlation rules to reduce alert storms."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RuleType(StrEnum):
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    TOPOLOGICAL = "topological"
    THRESHOLD = "threshold"
    COMPOSITE = "composite"


class CorrelationAction(StrEnum):
    SUPPRESS = "suppress"
    MERGE = "merge"
    ESCALATE = "escalate"
    REROUTE = "reroute"
    ANNOTATE = "annotate"


class RuleStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    TESTING = "testing"
    EXPIRED = "expired"
    ARCHIVED = "archived"


# --- Models ---


class CorrelationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    rule_type: RuleType = RuleType.TEMPORAL
    action: CorrelationAction = CorrelationAction.SUPPRESS
    status: RuleStatus = RuleStatus.ACTIVE
    source_pattern: str = ""
    target_pattern: str = ""
    time_window_seconds: int = 300
    priority: int = 0
    match_count: int = 0
    suppress_count: int = 0
    created_at: float = Field(default_factory=time.time)


class CorrelationMatch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str = ""
    source_alert: str = ""
    target_alert: str = ""
    action_taken: CorrelationAction = CorrelationAction.SUPPRESS
    matched_at: float = Field(default_factory=time.time)


class CorrelationReport(BaseModel):
    total_rules: int = 0
    active_rules: int = 0
    total_matches: int = 0
    total_suppressions: int = 0
    suppression_rate: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_rules: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertCorrelationRuleEngine:
    """Define and evaluate correlation rules to reduce alert storms."""

    def __init__(
        self,
        max_rules: int = 50000,
        time_window_seconds: int = 300,
    ) -> None:
        self._max_rules = max_rules
        self._time_window_seconds = time_window_seconds
        self._rules: list[CorrelationRule] = []
        self._matches: list[CorrelationMatch] = []
        logger.info(
            "alert_correlation_rules.initialized",
            max_rules=max_rules,
            time_window_seconds=time_window_seconds,
        )

    def register_rule(
        self,
        name: str,
        rule_type: RuleType,
        action: CorrelationAction,
        source_pattern: str = "",
        target_pattern: str = "",
        time_window_seconds: int = 300,
        priority: int = 0,
    ) -> CorrelationRule:
        """Register a new correlation rule."""
        rule = CorrelationRule(
            name=name,
            rule_type=rule_type,
            action=action,
            source_pattern=source_pattern,
            target_pattern=target_pattern,
            time_window_seconds=time_window_seconds,
            priority=priority,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_rules:
            self._rules = self._rules[-self._max_rules :]
        logger.info(
            "alert_correlation_rules.rule_registered",
            rule_id=rule.id,
            name=name,
            rule_type=rule_type,
            action=action,
        )
        return rule

    def get_rule(self, rule_id: str) -> CorrelationRule | None:
        """Retrieve a rule by ID."""
        for r in self._rules:
            if r.id == rule_id:
                return r
        return None

    def list_rules(
        self,
        rule_type: RuleType | None = None,
        status: RuleStatus | None = None,
        action: CorrelationAction | None = None,
        limit: int = 100,
    ) -> list[CorrelationRule]:
        """List rules with optional filtering."""
        results = list(self._rules)
        if rule_type is not None:
            results = [r for r in results if r.rule_type == rule_type]
        if status is not None:
            results = [r for r in results if r.status == status]
        if action is not None:
            results = [r for r in results if r.action == action]
        return results[-limit:]

    def evaluate_alert(
        self,
        alert_name: str,
        alert_source: str = "",
    ) -> list[CorrelationMatch]:
        """Evaluate an alert against all active rules."""
        matches: list[CorrelationMatch] = []
        for rule in self._rules:
            if rule.status != RuleStatus.ACTIVE:
                continue
            if not rule.source_pattern:
                continue
            # Check if source_pattern is a substring of alert_name or alert_source
            if rule.source_pattern in alert_name or (
                alert_source and rule.source_pattern in alert_source
            ):
                match = CorrelationMatch(
                    rule_id=rule.id,
                    source_alert=alert_name,
                    target_alert=rule.target_pattern,
                    action_taken=rule.action,
                )
                self._matches.append(match)
                matches.append(match)
                rule.match_count += 1
                if rule.action == CorrelationAction.SUPPRESS:
                    rule.suppress_count += 1
        logger.info(
            "alert_correlation_rules.alert_evaluated",
            alert_name=alert_name,
            match_count=len(matches),
        )
        return matches

    def find_correlated_alerts(self, alert_name: str) -> list[CorrelationMatch]:
        """Return matches where source_alert or target_alert contains alert_name."""
        results: list[CorrelationMatch] = []
        for match in self._matches:
            if alert_name in match.source_alert or alert_name in match.target_alert:
                results.append(match)
        return results

    def calculate_suppression_rate(self) -> dict[str, Any]:
        """Calculate the suppression rate across all matches."""
        total_matches = len(self._matches)
        total_suppressions = sum(
            1 for m in self._matches if m.action_taken == CorrelationAction.SUPPRESS
        )
        rate = round(total_suppressions / total_matches * 100, 2) if total_matches > 0 else 0.0
        return {
            "total_matches": total_matches,
            "total_suppressions": total_suppressions,
            "suppression_rate_pct": rate,
        }

    def detect_rule_conflicts(self) -> list[dict[str, Any]]:
        """Find rules with overlapping source_pattern and different actions."""
        conflicts: list[dict[str, Any]] = []
        active_rules = [r for r in self._rules if r.status == RuleStatus.ACTIVE]
        for i in range(len(active_rules)):
            for j in range(i + 1, len(active_rules)):
                rule_a = active_rules[i]
                rule_b = active_rules[j]
                if (
                    rule_a.source_pattern
                    and rule_b.source_pattern
                    and rule_a.source_pattern == rule_b.source_pattern
                    and rule_a.action != rule_b.action
                ):
                    conflicts.append(
                        {
                            "rule_a_id": rule_a.id,
                            "rule_b_id": rule_b.id,
                            "conflict_reason": (
                                f"Same source_pattern '{rule_a.source_pattern}' "
                                f"with different actions: {rule_a.action} vs {rule_b.action}"
                            ),
                        }
                    )
        logger.info(
            "alert_correlation_rules.conflicts_detected",
            conflict_count=len(conflicts),
        )
        return conflicts

    def rank_rules_by_effectiveness(self) -> list[CorrelationRule]:
        """Sort active rules by match_count descending."""
        active_rules = [r for r in self._rules if r.status == RuleStatus.ACTIVE]
        return sorted(active_rules, key=lambda r: r.match_count, reverse=True)

    def generate_correlation_report(self) -> CorrelationReport:
        """Generate a comprehensive correlation report."""
        total_rules = len(self._rules)
        active_rules = sum(1 for r in self._rules if r.status == RuleStatus.ACTIVE)
        total_matches = len(self._matches)
        total_suppressions = sum(
            1 for m in self._matches if m.action_taken == CorrelationAction.SUPPRESS
        )
        suppression_rate = (
            round(total_suppressions / total_matches * 100, 2) if total_matches > 0 else 0.0
        )

        # By type
        by_type: dict[str, int] = {}
        for r in self._rules:
            by_type[r.rule_type] = by_type.get(r.rule_type, 0) + 1

        # By action
        by_action: dict[str, int] = {}
        for r in self._rules:
            by_action[r.action] = by_action.get(r.action, 0) + 1

        # Top rules by match count
        ranked = self.rank_rules_by_effectiveness()[:5]
        top_rules = [
            {"rule_id": r.id, "name": r.name, "match_count": r.match_count} for r in ranked
        ]

        # Recommendations
        recommendations: list[str] = []
        if suppression_rate > 80:
            recommendations.append(
                "Suppression rate exceeds 80% — review rules for over-suppression"
            )
        conflicts = self.detect_rule_conflicts()
        if conflicts:
            recommendations.append(
                f"{len(conflicts)} rule conflict(s) detected — resolve overlapping patterns"
            )
        unused_rules = [
            r for r in self._rules if r.status == RuleStatus.ACTIVE and r.match_count == 0
        ]
        if unused_rules:
            recommendations.append(
                f"{len(unused_rules)} active rule(s) with zero matches — consider disabling"
            )

        logger.info(
            "alert_correlation_rules.report_generated",
            total_rules=total_rules,
            active_rules=active_rules,
            total_matches=total_matches,
        )
        return CorrelationReport(
            total_rules=total_rules,
            active_rules=active_rules,
            total_matches=total_matches,
            total_suppressions=total_suppressions,
            suppression_rate=suppression_rate,
            by_type=by_type,
            by_action=by_action,
            top_rules=top_rules,
            recommendations=recommendations,
        )

    def clear_data(self) -> None:
        """Clear all stored rules and matches."""
        self._rules.clear()
        self._matches.clear()
        logger.info("alert_correlation_rules.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        type_counts: dict[str, int] = {}
        action_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for r in self._rules:
            type_counts[r.rule_type] = type_counts.get(r.rule_type, 0) + 1
            action_counts[r.action] = action_counts.get(r.action, 0) + 1
            status_counts[r.status] = status_counts.get(r.status, 0) + 1
        return {
            "total_rules": len(self._rules),
            "total_matches": len(self._matches),
            "type_distribution": type_counts,
            "action_distribution": action_counts,
            "status_distribution": status_counts,
        }
