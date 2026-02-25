"""Deployment Rollback Advisor — analyze deployment health and advise on rollbacks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RollbackDecision(StrEnum):
    PROCEED = "proceed"
    MONITOR = "monitor"
    PREPARE_ROLLBACK = "prepare_rollback"
    ROLLBACK_NOW = "rollback_now"
    EMERGENCY_ROLLBACK = "emergency_rollback"


class HealthSignal(StrEnum):
    ERROR_RATE_SPIKE = "error_rate_spike"
    LATENCY_INCREASE = "latency_increase"
    CRASH_LOOP = "crash_loop"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DEPENDENCY_FAILURE = "dependency_failure"


class RollbackStrategy(StrEnum):
    FULL_ROLLBACK = "full_rollback"
    PARTIAL_ROLLBACK = "partial_rollback"
    FEATURE_FLAG_DISABLE = "feature_flag_disable"
    TRAFFIC_SHIFT = "traffic_shift"
    MANUAL_INTERVENTION = "manual_intervention"


# --- Models ---


class RollbackAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deployment_id: str = ""
    service_name: str = ""
    decision: RollbackDecision = RollbackDecision.PROCEED
    confidence: float = 0.0
    signals: list[str] = Field(default_factory=list)
    strategy: RollbackStrategy = RollbackStrategy.FULL_ROLLBACK
    blast_radius_pct: float = 0.0
    assessed_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class RollbackAction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    assessment_id: str = ""
    strategy: RollbackStrategy = RollbackStrategy.FULL_ROLLBACK
    executed_by: str = ""
    success: bool = False
    duration_seconds: int = 0
    executed_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class RollbackReport(BaseModel):
    total_assessments: int = 0
    total_rollbacks: int = 0
    rollback_rate_pct: float = 0.0
    avg_confidence: float = 0.0
    by_decision: dict[str, int] = Field(default_factory=dict)
    by_signal: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    slow_rollbacks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DeploymentRollbackAdvisor:
    """Analyze deployment health signals and advise on rollbacks."""

    def __init__(
        self,
        max_assessments: int = 100000,
        auto_rollback_confidence: float = 0.9,
    ) -> None:
        self._max_assessments = max_assessments
        self._auto_rollback_confidence = auto_rollback_confidence
        self._items: list[RollbackAssessment] = []
        self._actions: list[RollbackAction] = []
        logger.info(
            "rollback_advisor.initialized",
            max_assessments=max_assessments,
            auto_rollback_confidence=auto_rollback_confidence,
        )

    def create_assessment(
        self,
        deployment_id: str,
        service_name: str,
        signals: list[str] | None = None,
        blast_radius_pct: float = 0.0,
        **kw: Any,
    ) -> RollbackAssessment:
        """Create a rollback assessment for a deployment."""
        sig = signals or []
        assessment = RollbackAssessment(
            deployment_id=deployment_id,
            service_name=service_name,
            signals=sig,
            blast_radius_pct=blast_radius_pct,
            **kw,
        )
        self._items.append(assessment)
        if len(self._items) > self._max_assessments:
            self._items = self._items[-self._max_assessments :]
        logger.info(
            "rollback_advisor.assessment_created",
            assessment_id=assessment.id,
            deployment_id=deployment_id,
            service_name=service_name,
        )
        return assessment

    def get_assessment(
        self,
        assessment_id: str,
    ) -> RollbackAssessment | None:
        """Retrieve a single assessment by ID."""
        for a in self._items:
            if a.id == assessment_id:
                return a
        return None

    def list_assessments(
        self,
        service_name: str | None = None,
        decision: RollbackDecision | None = None,
        limit: int = 50,
    ) -> list[RollbackAssessment]:
        """List assessments with optional filtering."""
        results = list(self._items)
        if service_name is not None:
            results = [a for a in results if a.service_name == service_name]
        if decision is not None:
            results = [a for a in results if a.decision == decision]
        return results[-limit:]

    def evaluate_rollback_need(
        self,
        assessment_id: str,
    ) -> RollbackAssessment | None:
        """Evaluate health signals and set decision + confidence.

        Decision logic based on signal count and types:
        - 3+ signals or crash_loop -> EMERGENCY_ROLLBACK
        - 2 signals -> ROLLBACK_NOW
        - 1 signal -> PREPARE_ROLLBACK if high-impact, else MONITOR
        - 0 signals -> PROCEED
        """
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return None

        sig_count = len(assessment.signals)
        has_crash = HealthSignal.CRASH_LOOP in assessment.signals
        has_resource = HealthSignal.RESOURCE_EXHAUSTION in assessment.signals

        if sig_count >= 3 or has_crash:
            assessment.decision = RollbackDecision.EMERGENCY_ROLLBACK
            assessment.confidence = min(0.99, 0.7 + sig_count * 0.08)
            assessment.strategy = RollbackStrategy.FULL_ROLLBACK
        elif sig_count == 2:
            assessment.decision = RollbackDecision.ROLLBACK_NOW
            assessment.confidence = min(0.95, 0.6 + sig_count * 0.1)
            assessment.strategy = RollbackStrategy.FULL_ROLLBACK
        elif sig_count == 1:
            if has_resource:
                assessment.decision = RollbackDecision.PREPARE_ROLLBACK
                assessment.confidence = 0.65
                assessment.strategy = RollbackStrategy.TRAFFIC_SHIFT
            else:
                assessment.decision = RollbackDecision.MONITOR
                assessment.confidence = 0.5
                assessment.strategy = RollbackStrategy.FEATURE_FLAG_DISABLE
        else:
            assessment.decision = RollbackDecision.PROCEED
            assessment.confidence = 0.95
            assessment.strategy = RollbackStrategy.MANUAL_INTERVENTION

        assessment.confidence = round(assessment.confidence, 2)
        logger.info(
            "rollback_advisor.evaluated",
            assessment_id=assessment_id,
            decision=assessment.decision,
            confidence=assessment.confidence,
        )
        return assessment

    def execute_rollback(
        self,
        assessment_id: str,
        strategy: RollbackStrategy,
        executed_by: str,
    ) -> RollbackAction | None:
        """Record a rollback execution for an assessment."""
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return None

        # Simulate duration based on strategy
        duration_map = {
            RollbackStrategy.FULL_ROLLBACK: 120,
            RollbackStrategy.PARTIAL_ROLLBACK: 90,
            RollbackStrategy.FEATURE_FLAG_DISABLE: 10,
            RollbackStrategy.TRAFFIC_SHIFT: 60,
            RollbackStrategy.MANUAL_INTERVENTION: 300,
        }
        duration = duration_map.get(strategy, 120)

        action = RollbackAction(
            assessment_id=assessment_id,
            strategy=strategy,
            executed_by=executed_by,
            success=True,
            duration_seconds=duration,
        )
        self._actions.append(action)
        if len(self._actions) > self._max_assessments:
            self._actions = self._actions[-self._max_assessments :]
        logger.info(
            "rollback_advisor.rollback_executed",
            assessment_id=assessment_id,
            strategy=strategy,
            executed_by=executed_by,
            duration_seconds=duration,
        )
        return action

    def calculate_rollback_success_rate(self) -> float:
        """Calculate the success rate of executed rollbacks."""
        if not self._actions:
            return 0.0
        ok = sum(1 for a in self._actions if a.success)
        return round(ok / len(self._actions) * 100, 2)

    def identify_rollback_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Identify services with recurring rollback needs."""
        svc_counts: dict[str, dict[str, Any]] = {}
        for a in self._items:
            if a.decision in (
                RollbackDecision.ROLLBACK_NOW,
                RollbackDecision.EMERGENCY_ROLLBACK,
            ):
                if a.service_name not in svc_counts:
                    svc_counts[a.service_name] = {
                        "service_name": a.service_name,
                        "rollback_count": 0,
                        "avg_confidence": 0.0,
                        "signals": [],
                    }
                entry = svc_counts[a.service_name]
                entry["rollback_count"] += 1
                entry["signals"].extend(a.signals)

        for entry in svc_counts.values():
            rollback_assessments = [
                a
                for a in self._items
                if a.service_name == entry["service_name"]
                and a.decision
                in (
                    RollbackDecision.ROLLBACK_NOW,
                    RollbackDecision.EMERGENCY_ROLLBACK,
                )
            ]
            if rollback_assessments:
                avg = sum(a.confidence for a in rollback_assessments) / len(rollback_assessments)
                entry["avg_confidence"] = round(avg, 2)
            entry["signals"] = list(set(entry["signals"]))

        patterns = sorted(
            svc_counts.values(),
            key=lambda x: x["rollback_count"],
            reverse=True,
        )
        return patterns

    def estimate_rollback_time(
        self,
        service_name: str,
    ) -> dict[str, Any]:
        """Estimate rollback duration based on history."""
        svc_actions = [
            a
            for a in self._actions
            if any(
                ass.service_name == service_name and ass.id == a.assessment_id
                for ass in self._items
            )
        ]
        if not svc_actions:
            return {
                "service_name": service_name,
                "avg_duration_seconds": 0,
                "min_duration_seconds": 0,
                "max_duration_seconds": 0,
                "sample_count": 0,
            }
        durations = [a.duration_seconds for a in svc_actions]
        return {
            "service_name": service_name,
            "avg_duration_seconds": round(sum(durations) / len(durations), 1),
            "min_duration_seconds": min(durations),
            "max_duration_seconds": max(durations),
            "sample_count": len(durations),
        }

    def generate_rollback_report(self) -> RollbackReport:
        """Generate a comprehensive rollback report."""
        total = len(self._items)
        rollback_decisions = [
            a
            for a in self._items
            if a.decision
            in (
                RollbackDecision.ROLLBACK_NOW,
                RollbackDecision.EMERGENCY_ROLLBACK,
            )
        ]
        total_rb = len(rollback_decisions)
        rate = round(total_rb / total * 100, 2) if total else 0.0

        avg_conf = 0.0
        if self._items:
            avg_conf = round(
                sum(a.confidence for a in self._items) / len(self._items),
                2,
            )

        by_decision: dict[str, int] = {}
        by_signal: dict[str, int] = {}
        for a in self._items:
            by_decision[a.decision.value] = by_decision.get(a.decision.value, 0) + 1
            for s in a.signals:
                by_signal[s] = by_signal.get(s, 0) + 1

        by_strategy: dict[str, int] = {}
        slow_ids: list[str] = []
        for act in self._actions:
            by_strategy[act.strategy.value] = by_strategy.get(act.strategy.value, 0) + 1
            if act.duration_seconds > 180:
                slow_ids.append(act.id)

        recommendations: list[str] = []
        if rate > 20:
            recommendations.append(
                f"Rollback rate {rate:.1f}% exceeds 20% — improve pre-deployment validation"
            )
        if slow_ids:
            recommendations.append(
                f"{len(slow_ids)} rollback(s) took >3 min — optimize rollback automation"
            )
        patterns = self.identify_rollback_patterns()
        if patterns:
            top = patterns[0]
            recommendations.append(
                f"{top['service_name']} has"
                f" {top['rollback_count']} rollback(s)"
                " — investigate root cause"
            )

        report = RollbackReport(
            total_assessments=total,
            total_rollbacks=total_rb,
            rollback_rate_pct=rate,
            avg_confidence=avg_conf,
            by_decision=by_decision,
            by_signal=by_signal,
            by_strategy=by_strategy,
            slow_rollbacks=slow_ids,
            recommendations=recommendations,
        )
        logger.info(
            "rollback_advisor.report_generated",
            total_assessments=total,
            total_rollbacks=total_rb,
            rollback_rate_pct=rate,
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored assessments and actions."""
        self._items.clear()
        self._actions.clear()
        logger.info("rollback_advisor.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        decision_counts: dict[str, int] = {}
        service_counts: dict[str, int] = {}
        for a in self._items:
            decision_counts[a.decision.value] = decision_counts.get(a.decision.value, 0) + 1
            service_counts[a.service_name] = service_counts.get(a.service_name, 0) + 1
        return {
            "total_assessments": len(self._items),
            "total_actions": len(self._actions),
            "decision_distribution": decision_counts,
            "service_distribution": service_counts,
            "max_assessments": self._max_assessments,
            "auto_rollback_confidence": (self._auto_rollback_confidence),
        }
