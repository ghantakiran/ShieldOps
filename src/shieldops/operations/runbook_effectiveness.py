"""Runbook Effectiveness Analyzer — score runbook outcomes, detect decay, suggest improvements."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EffectivenessRating(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    INEFFECTIVE = "ineffective"


class FailureReason(StrEnum):
    OUTDATED_STEPS = "outdated_steps"
    MISSING_CONTEXT = "missing_context"
    WRONG_DIAGNOSIS = "wrong_diagnosis"
    PERMISSION_ERROR = "permission_error"
    TIMEOUT = "timeout"
    INFRASTRUCTURE_CHANGE = "infrastructure_change"


class ImprovementType(StrEnum):
    ADD_STEP = "add_step"
    REMOVE_STEP = "remove_step"
    UPDATE_COMMAND = "update_command"
    ADD_VALIDATION = "add_validation"
    AUTOMATE = "automate"


# --- Models ---


class RunbookOutcome(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    runbook_name: str = ""
    executed_by: str = ""
    success: bool = True
    execution_time_seconds: float = 0.0
    failure_reason: FailureReason | None = None
    notes: str = ""
    executed_at: float = Field(default_factory=time.time)


class EffectivenessScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    runbook_name: str = ""
    total_executions: int = 0
    success_count: int = 0
    avg_execution_time: float = 0.0
    success_rate: float = 0.0
    rating: EffectivenessRating = EffectivenessRating.FAIR
    trend: str = "stable"
    calculated_at: float = Field(default_factory=time.time)


class EffectivenessReport(BaseModel):
    total_runbooks: int = 0
    total_executions: int = 0
    avg_success_rate: float = 0.0
    decaying_count: int = 0
    rating_distribution: dict[str, int] = Field(default_factory=dict)
    top_failure_reasons: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RunbookEffectivenessAnalyzer:
    """Score runbook outcomes, detect effectiveness decay, and suggest improvements."""

    def __init__(
        self,
        max_outcomes: int = 200000,
        decay_window_days: int = 90,
    ) -> None:
        self._max_outcomes = max_outcomes
        self._decay_window_days = decay_window_days
        self._outcomes: list[RunbookOutcome] = []
        logger.info(
            "runbook_effectiveness.initialized",
            max_outcomes=max_outcomes,
            decay_window_days=decay_window_days,
        )

    def record_outcome(
        self,
        runbook_id: str,
        runbook_name: str,
        executed_by: str,
        success: bool = True,
        execution_time_seconds: float = 0.0,
        failure_reason: FailureReason | None = None,
        notes: str = "",
    ) -> RunbookOutcome:
        """Record the outcome of a runbook execution."""
        outcome = RunbookOutcome(
            runbook_id=runbook_id,
            runbook_name=runbook_name,
            executed_by=executed_by,
            success=success,
            execution_time_seconds=execution_time_seconds,
            failure_reason=failure_reason,
            notes=notes,
        )
        self._outcomes.append(outcome)
        if len(self._outcomes) > self._max_outcomes:
            self._outcomes = self._outcomes[-self._max_outcomes :]
        logger.info(
            "runbook_effectiveness.outcome_recorded",
            outcome_id=outcome.id,
            runbook_id=runbook_id,
            runbook_name=runbook_name,
            success=success,
        )
        return outcome

    def get_outcome(self, outcome_id: str) -> RunbookOutcome | None:
        """Retrieve a single outcome by ID."""
        for o in self._outcomes:
            if o.id == outcome_id:
                return o
        return None

    def list_outcomes(
        self,
        runbook_id: str | None = None,
        success: bool | None = None,
        limit: int = 100,
    ) -> list[RunbookOutcome]:
        """List outcomes with optional filtering by runbook and success status."""
        results = list(self._outcomes)
        if runbook_id is not None:
            results = [o for o in results if o.runbook_id == runbook_id]
        if success is not None:
            results = [o for o in results if o.success == success]
        return results[-limit:]

    def calculate_effectiveness(self, runbook_id: str) -> EffectivenessScore:
        """Compute the effectiveness score for a specific runbook.

        Rating thresholds:
            >= 90% success -> EXCELLENT
            >= 75% success -> GOOD
            >= 60% success -> FAIR
            >= 40% success -> POOR
            < 40% success  -> INEFFECTIVE

        Trend is determined by comparing the success rate of the recent half
        of executions against the older half. A difference greater than 10%
        marks the trend as improving or declining.
        """
        executions = [o for o in self._outcomes if o.runbook_id == runbook_id]
        total = len(executions)
        if total == 0:
            return EffectivenessScore(runbook_id=runbook_id)

        # Derive the runbook name from the most recent execution
        runbook_name = executions[-1].runbook_name
        success_count = sum(1 for o in executions if o.success)
        total_time = sum(o.execution_time_seconds for o in executions)
        avg_time = round(total_time / total, 2)
        success_rate = round(success_count / total * 100, 2)

        # Determine rating
        if success_rate >= 90.0:
            rating = EffectivenessRating.EXCELLENT
        elif success_rate >= 75.0:
            rating = EffectivenessRating.GOOD
        elif success_rate >= 60.0:
            rating = EffectivenessRating.FAIR
        elif success_rate >= 40.0:
            rating = EffectivenessRating.POOR
        else:
            rating = EffectivenessRating.INEFFECTIVE

        # Determine trend by comparing older half vs recent half
        trend = "stable"
        if total >= 4:
            midpoint = total // 2
            older_half = executions[:midpoint]
            recent_half = executions[midpoint:]
            older_rate = sum(1 for o in older_half if o.success) / len(older_half) * 100
            recent_rate = sum(1 for o in recent_half if o.success) / len(recent_half) * 100
            diff = recent_rate - older_rate
            if diff > 10.0:
                trend = "improving"
            elif diff < -10.0:
                trend = "declining"

        score = EffectivenessScore(
            runbook_id=runbook_id,
            runbook_name=runbook_name,
            total_executions=total,
            success_count=success_count,
            avg_execution_time=avg_time,
            success_rate=success_rate,
            rating=rating,
            trend=trend,
        )
        logger.info(
            "runbook_effectiveness.score_calculated",
            runbook_id=runbook_id,
            success_rate=success_rate,
            rating=rating,
            trend=trend,
        )
        return score

    def detect_runbook_decay(self) -> list[EffectivenessScore]:
        """Identify runbooks with a declining effectiveness trend.

        Only considers outcomes within the configured decay window (default 90 days).
        A declining trend indicates the runbook may be outdated or environmental
        conditions have changed.
        """
        cutoff = time.time() - (self._decay_window_days * 86400)
        recent_outcomes = [o for o in self._outcomes if o.executed_at >= cutoff]

        # Collect unique runbook IDs from recent outcomes
        runbook_ids: set[str] = {o.runbook_id for o in recent_outcomes}
        decaying: list[EffectivenessScore] = []

        for rb_id in runbook_ids:
            score = self.calculate_effectiveness(rb_id)
            if score.trend == "declining":
                decaying.append(score)

        decaying.sort(key=lambda s: s.success_rate)
        logger.info(
            "runbook_effectiveness.decay_detected",
            decaying_count=len(decaying),
        )
        return decaying

    def analyze_failure_patterns(self) -> list[dict[str, Any]]:
        """Group failed executions by failure reason with counts, sorted descending.

        Returns a list of dicts containing the reason, count, affected runbooks,
        and the percentage share of all failures.
        """
        failures = [o for o in self._outcomes if not o.success and o.failure_reason]
        if not failures:
            return []

        reason_data: dict[str, dict[str, Any]] = {}
        for o in failures:
            reason = o.failure_reason.value  # type: ignore[union-attr]
            if reason not in reason_data:
                reason_data[reason] = {"count": 0, "runbooks": set()}
            reason_data[reason]["count"] += 1
            reason_data[reason]["runbooks"].add(o.runbook_id)

        total_failures = len(failures)
        patterns: list[dict[str, Any]] = []
        for reason, data in reason_data.items():
            patterns.append(
                {
                    "failure_reason": reason,
                    "count": data["count"],
                    "affected_runbooks": len(data["runbooks"]),
                    "pct_of_failures": round(data["count"] / total_failures * 100, 1),
                }
            )

        patterns.sort(key=lambda x: x["count"], reverse=True)
        return patterns

    def suggest_improvements(self, runbook_id: str) -> list[dict[str, Any]]:
        """Suggest improvements for a specific runbook based on its failure patterns.

        Mapping:
            OUTDATED_STEPS      -> UPDATE_COMMAND
            MISSING_CONTEXT     -> ADD_STEP
            WRONG_DIAGNOSIS     -> ADD_VALIDATION
            PERMISSION_ERROR    -> ADD_STEP
            TIMEOUT             -> AUTOMATE
            INFRASTRUCTURE_CHANGE -> UPDATE_COMMAND
        """
        reason_to_improvement: dict[FailureReason, tuple[ImprovementType, str]] = {
            FailureReason.OUTDATED_STEPS: (
                ImprovementType.UPDATE_COMMAND,
                "Update outdated commands and tool references to current versions",
            ),
            FailureReason.MISSING_CONTEXT: (
                ImprovementType.ADD_STEP,
                "Add prerequisite checks and context-gathering steps at the beginning",
            ),
            FailureReason.WRONG_DIAGNOSIS: (
                ImprovementType.ADD_VALIDATION,
                "Add diagnostic validation steps to confirm root cause before remediation",
            ),
            FailureReason.PERMISSION_ERROR: (
                ImprovementType.ADD_STEP,
                "Add permission verification steps and required role documentation",
            ),
            FailureReason.TIMEOUT: (
                ImprovementType.AUTOMATE,
                "Automate time-consuming manual steps to reduce execution time",
            ),
            FailureReason.INFRASTRUCTURE_CHANGE: (
                ImprovementType.UPDATE_COMMAND,
                "Update infrastructure references to reflect current topology and endpoints",
            ),
        }

        failures = [
            o
            for o in self._outcomes
            if o.runbook_id == runbook_id and not o.success and o.failure_reason
        ]
        if not failures:
            return []

        # Count occurrences per failure reason
        reason_counts: dict[FailureReason, int] = {}
        for o in failures:
            reason = o.failure_reason
            if reason is None:
                continue
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        suggestions: list[dict[str, Any]] = []
        for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
            improvement_type, description = reason_to_improvement.get(
                reason,
                (ImprovementType.ADD_VALIDATION, "Review and update runbook steps"),
            )
            suggestions.append(
                {
                    "failure_reason": reason.value,
                    "occurrence_count": count,
                    "improvement_type": improvement_type.value,
                    "suggestion": description,
                    "priority": "high" if count >= 3 else "medium" if count >= 2 else "low",
                }
            )

        return suggestions

    def rank_runbooks_by_effectiveness(self) -> list[EffectivenessScore]:
        """Calculate effectiveness scores for all runbooks, sorted by success_rate descending."""
        runbook_ids: set[str] = {o.runbook_id for o in self._outcomes}
        scores: list[EffectivenessScore] = []
        for rb_id in runbook_ids:
            score = self.calculate_effectiveness(rb_id)
            scores.append(score)
        scores.sort(key=lambda s: s.success_rate, reverse=True)
        return scores

    def generate_effectiveness_report(self) -> EffectivenessReport:
        """Generate a comprehensive runbook effectiveness report."""
        runbook_ids: set[str] = {o.runbook_id for o in self._outcomes}
        total_runbooks = len(runbook_ids)
        total_executions = len(self._outcomes)

        # Calculate per-runbook scores
        scores = self.rank_runbooks_by_effectiveness()
        avg_success = round(sum(s.success_rate for s in scores) / len(scores), 2) if scores else 0.0

        # Decaying runbooks
        decaying = self.detect_runbook_decay()

        # Rating distribution
        rating_dist: dict[str, int] = {}
        for s in scores:
            key = s.rating.value
            rating_dist[key] = rating_dist.get(key, 0) + 1

        # Top failure reasons
        failure_patterns = self.analyze_failure_patterns()
        top_reasons = [p["failure_reason"] for p in failure_patterns[:5]]

        # Build recommendations
        recommendations: list[str] = []
        if decaying:
            recommendations.append(
                f"{len(decaying)} runbook(s) show declining effectiveness — "
                f"review and update their steps"
            )

        ineffective = [s for s in scores if s.rating == EffectivenessRating.INEFFECTIVE]
        if ineffective:
            names = [s.runbook_name or s.runbook_id for s in ineffective[:5]]
            recommendations.append(f"Ineffective runbooks requiring rewrite: {', '.join(names)}")

        if failure_patterns:
            top = failure_patterns[0]
            recommendations.append(
                f"Most common failure reason is '{top['failure_reason']}' "
                f"({top['count']} occurrences) — prioritize addressing this pattern"
            )

        poor_or_worse = [
            s
            for s in scores
            if s.rating in (EffectivenessRating.POOR, EffectivenessRating.INEFFECTIVE)
        ]
        if total_runbooks > 0 and len(poor_or_worse) / total_runbooks > 0.3:
            recommendations.append(
                "Over 30% of runbooks are rated POOR or INEFFECTIVE — "
                "consider a runbook audit initiative"
            )

        report = EffectivenessReport(
            total_runbooks=total_runbooks,
            total_executions=total_executions,
            avg_success_rate=avg_success,
            decaying_count=len(decaying),
            rating_distribution=rating_dist,
            top_failure_reasons=top_reasons,
            recommendations=recommendations,
        )
        logger.info(
            "runbook_effectiveness.report_generated",
            total_runbooks=total_runbooks,
            total_executions=total_executions,
            avg_success_rate=avg_success,
            decaying_count=len(decaying),
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored outcomes."""
        self._outcomes.clear()
        logger.info("runbook_effectiveness.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about stored outcomes."""
        runbook_ids: set[str] = set()
        executors: set[str] = set()
        success_count = 0
        failure_count = 0
        for o in self._outcomes:
            runbook_ids.add(o.runbook_id)
            executors.add(o.executed_by)
            if o.success:
                success_count += 1
            else:
                failure_count += 1
        return {
            "total_outcomes": len(self._outcomes),
            "unique_runbooks": len(runbook_ids),
            "unique_executors": len(executors),
            "success_count": success_count,
            "failure_count": failure_count,
        }
