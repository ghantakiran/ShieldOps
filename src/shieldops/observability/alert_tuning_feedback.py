"""Alert Tuning Feedback Loop — closed-loop feedback for alert rule effectiveness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AlertFeedback(StrEnum):
    ACTIONABLE = "actionable"
    INFORMATIONAL = "informational"
    NOISY = "noisy"
    DUPLICATE = "duplicate"
    MISSED_INCIDENT = "missed_incident"


class TuningAction(StrEnum):
    TIGHTEN_THRESHOLD = "tighten_threshold"
    RELAX_THRESHOLD = "relax_threshold"
    ADD_FILTER = "add_filter"
    DISABLE_RULE = "disable_rule"
    NO_CHANGE = "no_change"


class RuleHealth(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    NEEDS_TUNING = "needs_tuning"
    POOR = "poor"
    BROKEN = "broken"


# --- Models ---


class AlertFeedbackRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    alert_id: str = ""
    feedback: AlertFeedback = AlertFeedback.ACTIONABLE
    responder_id: str = ""
    comment: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertRuleEffectiveness(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    total_alerts: int = 0
    actionable_count: int = 0
    noisy_count: int = 0
    duplicate_count: int = 0
    precision_pct: float = 0.0
    health: RuleHealth = RuleHealth.GOOD
    recommended_action: TuningAction = TuningAction.NO_CHANGE
    created_at: float = Field(default_factory=time.time)


class AlertTuningReport(BaseModel):
    total_feedback: int = 0
    total_rules_evaluated: int = 0
    avg_precision_pct: float = 0.0
    noisy_rule_count: int = 0
    by_feedback: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertTuningFeedbackLoop:
    """Closed-loop feedback system for alert rule effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        precision_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._precision_threshold = precision_threshold
        self._feedback: list[AlertFeedbackRecord] = []
        self._effectiveness: list[AlertRuleEffectiveness] = []
        logger.info(
            "alert_tuning_feedback.initialized",
            max_records=max_records,
            precision_threshold=precision_threshold,
        )

    # -- internal helpers ------------------------------------------------

    def _precision_to_health(self, precision: float) -> RuleHealth:
        if precision >= 90:
            return RuleHealth.EXCELLENT
        if precision >= 75:
            return RuleHealth.GOOD
        if precision >= 50:
            return RuleHealth.NEEDS_TUNING
        if precision >= 25:
            return RuleHealth.POOR
        return RuleHealth.BROKEN

    def _health_to_action(self, health: RuleHealth) -> TuningAction:
        return {
            RuleHealth.EXCELLENT: TuningAction.NO_CHANGE,
            RuleHealth.GOOD: TuningAction.NO_CHANGE,
            RuleHealth.NEEDS_TUNING: TuningAction.TIGHTEN_THRESHOLD,
            RuleHealth.POOR: TuningAction.ADD_FILTER,
            RuleHealth.BROKEN: TuningAction.DISABLE_RULE,
        }.get(health, TuningAction.NO_CHANGE)

    # -- record / get / list ---------------------------------------------

    def record_feedback(
        self,
        rule_name: str,
        alert_id: str = "",
        feedback: AlertFeedback = AlertFeedback.ACTIONABLE,
        responder_id: str = "",
        comment: str = "",
    ) -> AlertFeedbackRecord:
        record = AlertFeedbackRecord(
            rule_name=rule_name,
            alert_id=alert_id,
            feedback=feedback,
            responder_id=responder_id,
            comment=comment,
        )
        self._feedback.append(record)
        if len(self._feedback) > self._max_records:
            self._feedback = self._feedback[-self._max_records :]
        logger.info(
            "alert_tuning_feedback.feedback_recorded",
            record_id=record.id,
            rule_name=rule_name,
            feedback=feedback.value,
        )
        return record

    def get_feedback(self, record_id: str) -> AlertFeedbackRecord | None:
        for f in self._feedback:
            if f.id == record_id:
                return f
        return None

    def list_feedback(
        self,
        rule_name: str | None = None,
        feedback: AlertFeedback | None = None,
        limit: int = 50,
    ) -> list[AlertFeedbackRecord]:
        results = list(self._feedback)
        if rule_name is not None:
            results = [f for f in results if f.rule_name == rule_name]
        if feedback is not None:
            results = [f for f in results if f.feedback == feedback]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def evaluate_rule_effectiveness(self, rule_name: str) -> AlertRuleEffectiveness:
        """Evaluate effectiveness of a specific alert rule."""
        rule_feedback = [f for f in self._feedback if f.rule_name == rule_name]
        total = len(rule_feedback)
        if total == 0:
            eff = AlertRuleEffectiveness(
                rule_name=rule_name,
                health=RuleHealth.GOOD,
                recommended_action=TuningAction.NO_CHANGE,
            )
            self._effectiveness.append(eff)
            return eff

        actionable = sum(1 for f in rule_feedback if f.feedback == AlertFeedback.ACTIONABLE)
        noisy = sum(1 for f in rule_feedback if f.feedback == AlertFeedback.NOISY)
        duplicate = sum(1 for f in rule_feedback if f.feedback == AlertFeedback.DUPLICATE)
        precision = round(actionable / total * 100, 2)
        health = self._precision_to_health(precision)
        action = self._health_to_action(health)

        eff = AlertRuleEffectiveness(
            rule_name=rule_name,
            total_alerts=total,
            actionable_count=actionable,
            noisy_count=noisy,
            duplicate_count=duplicate,
            precision_pct=precision,
            health=health,
            recommended_action=action,
        )
        self._effectiveness.append(eff)
        if len(self._effectiveness) > self._max_records:
            self._effectiveness = self._effectiveness[-self._max_records :]
        logger.info(
            "alert_tuning_feedback.rule_evaluated",
            rule_name=rule_name,
            precision=precision,
            health=health.value,
        )
        return eff

    def identify_noisy_rules(self) -> list[dict[str, Any]]:
        """Find rules with high noise ratio."""
        rule_noise: dict[str, dict[str, int]] = {}
        for f in self._feedback:
            if f.rule_name not in rule_noise:
                rule_noise[f.rule_name] = {"total": 0, "noisy": 0, "duplicate": 0}
            rule_noise[f.rule_name]["total"] += 1
            if f.feedback == AlertFeedback.NOISY:
                rule_noise[f.rule_name]["noisy"] += 1
            if f.feedback == AlertFeedback.DUPLICATE:
                rule_noise[f.rule_name]["duplicate"] += 1

        results: list[dict[str, Any]] = []
        for rule, counts in rule_noise.items():
            noise_rate = round((counts["noisy"] + counts["duplicate"]) / counts["total"] * 100, 2)
            if noise_rate > (100 - self._precision_threshold):
                results.append(
                    {
                        "rule_name": rule,
                        "total_alerts": counts["total"],
                        "noisy_count": counts["noisy"],
                        "duplicate_count": counts["duplicate"],
                        "noise_rate_pct": noise_rate,
                    }
                )
        results.sort(key=lambda x: x["noise_rate_pct"], reverse=True)
        return results

    def identify_blind_spots(self) -> list[dict[str, Any]]:
        """Find missed incidents (alerts that should have fired but didn't)."""
        missed = [f for f in self._feedback if f.feedback == AlertFeedback.MISSED_INCIDENT]
        rule_missed: dict[str, int] = {}
        for f in missed:
            rule_missed[f.rule_name] = rule_missed.get(f.rule_name, 0) + 1
        return [
            {"rule_name": rule, "missed_count": count}
            for rule, count in sorted(rule_missed.items(), key=lambda x: x[1], reverse=True)
        ]

    def recommend_tuning_actions(self) -> list[dict[str, Any]]:
        """Recommend tuning actions for all evaluated rules."""
        rules = {f.rule_name for f in self._feedback}
        results: list[dict[str, Any]] = []
        for rule in rules:
            eff = self.evaluate_rule_effectiveness(rule)
            if eff.recommended_action != TuningAction.NO_CHANGE:
                results.append(
                    {
                        "rule_name": rule,
                        "health": eff.health.value,
                        "precision_pct": eff.precision_pct,
                        "recommended_action": eff.recommended_action.value,
                        "noisy_count": eff.noisy_count,
                    }
                )
        results.sort(key=lambda x: x["precision_pct"])
        return results

    def calculate_rule_health(self, rule_name: str) -> dict[str, Any]:
        """Calculate health metrics for a specific rule."""
        eff = self.evaluate_rule_effectiveness(rule_name)
        return {
            "rule_name": rule_name,
            "health": eff.health.value,
            "precision_pct": eff.precision_pct,
            "total_alerts": eff.total_alerts,
            "actionable_count": eff.actionable_count,
            "noisy_count": eff.noisy_count,
            "duplicate_count": eff.duplicate_count,
            "recommended_action": eff.recommended_action.value,
        }

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> AlertTuningReport:
        by_feedback: dict[str, int] = {}
        for f in self._feedback:
            by_feedback[f.feedback.value] = by_feedback.get(f.feedback.value, 0) + 1
        # Evaluate all rules
        rules = {f.rule_name for f in self._feedback}
        by_health: dict[str, int] = {}
        total_precision = 0.0
        noisy_rule_count = 0
        for rule in rules:
            eff = self.evaluate_rule_effectiveness(rule)
            by_health[eff.health.value] = by_health.get(eff.health.value, 0) + 1
            total_precision += eff.precision_pct
            if eff.health in (RuleHealth.POOR, RuleHealth.BROKEN):
                noisy_rule_count += 1
        avg_precision = round(total_precision / len(rules), 2) if rules else 0.0
        recs: list[str] = []
        if noisy_rule_count > 0:
            recs.append(f"{noisy_rule_count} rule(s) need tuning or disabling")
        if avg_precision < self._precision_threshold:
            recs.append(
                f"Average precision {avg_precision}% below threshold {self._precision_threshold}%"
            )
        missed = by_feedback.get(AlertFeedback.MISSED_INCIDENT.value, 0)
        if missed > 0:
            recs.append(f"{missed} missed incident(s) — review alert coverage")
        if not recs:
            recs.append("Alert rules performing within acceptable parameters")
        return AlertTuningReport(
            total_feedback=len(self._feedback),
            total_rules_evaluated=len(rules),
            avg_precision_pct=avg_precision,
            noisy_rule_count=noisy_rule_count,
            by_feedback=by_feedback,
            by_health=by_health,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._feedback.clear()
        self._effectiveness.clear()
        logger.info("alert_tuning_feedback.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        feedback_dist: dict[str, int] = {}
        for f in self._feedback:
            key = f.feedback.value
            feedback_dist[key] = feedback_dist.get(key, 0) + 1
        return {
            "total_feedback": len(self._feedback),
            "total_effectiveness": len(self._effectiveness),
            "precision_threshold": self._precision_threshold,
            "feedback_distribution": feedback_dist,
            "unique_rules": len({f.rule_name for f in self._feedback}),
        }
