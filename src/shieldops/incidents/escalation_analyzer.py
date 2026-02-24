"""Escalation Pattern Analyzer — escalation effectiveness, pattern detection, recommendations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EscalationReason(StrEnum):
    TIMEOUT = "timeout"
    SEVERITY_INCREASE = "severity_increase"
    CUSTOMER_IMPACT = "customer_impact"
    SKILL_GAP = "skill_gap"
    POLICY_REQUIRED = "policy_required"
    MANUAL = "manual"


class EscalationOutcome(StrEnum):
    RESOLVED = "resolved"
    FURTHER_ESCALATED = "further_escalated"
    DOWNGRADED = "downgraded"
    TIMED_OUT = "timed_out"
    FALSE_ALARM = "false_alarm"


class EscalationTier(StrEnum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    MANAGEMENT = "management"
    EXECUTIVE = "executive"


# --- Models ---


class EscalationEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    from_tier: EscalationTier = EscalationTier.L1
    to_tier: EscalationTier = EscalationTier.L2
    reason: EscalationReason = EscalationReason.MANUAL
    outcome: EscalationOutcome | None = None
    service: str = ""
    escalated_at: float = Field(default_factory=time.time)
    resolved_at: float | None = None


class EscalationPattern(BaseModel):
    pattern_type: str
    occurrence_count: int = 0
    services: list[str] = Field(default_factory=list)
    avg_resolution_time_seconds: float = 0.0
    description: str = ""


class EscalationEfficiencyReport(BaseModel):
    total_escalations: int = 0
    resolved_count: int = 0
    false_alarm_count: int = 0
    false_alarm_rate: float = 0.0
    avg_resolution_time_seconds: float = 0.0
    tier_breakdown: dict[str, int] = Field(default_factory=dict)
    bottleneck_tier: str = ""
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EscalationPatternAnalyzer:
    """Escalation effectiveness analysis, pattern detection, and improvement recommendations."""

    def __init__(
        self,
        max_events: int = 100000,
        false_alarm_threshold: float = 0.3,
    ) -> None:
        self._max_events = max_events
        self._false_alarm_threshold = false_alarm_threshold
        self._escalations: list[EscalationEvent] = []
        logger.info(
            "escalation_analyzer.initialized",
            max_events=max_events,
            false_alarm_threshold=false_alarm_threshold,
        )

    def record_escalation(
        self,
        incident_id: str = "",
        from_tier: EscalationTier = EscalationTier.L1,
        to_tier: EscalationTier = EscalationTier.L2,
        reason: EscalationReason = EscalationReason.MANUAL,
        service: str = "",
    ) -> EscalationEvent:
        """Record a new escalation event, evicting oldest if over max."""
        event = EscalationEvent(
            incident_id=incident_id,
            from_tier=from_tier,
            to_tier=to_tier,
            reason=reason,
            service=service,
        )
        self._escalations.append(event)
        if len(self._escalations) > self._max_events:
            self._escalations = self._escalations[-self._max_events :]
        logger.info(
            "escalation_analyzer.recorded",
            escalation_id=event.id,
            incident_id=incident_id,
            from_tier=from_tier,
            to_tier=to_tier,
        )
        return event

    def get_escalation(self, escalation_id: str) -> EscalationEvent | None:
        """Retrieve a single escalation by ID."""
        for esc in self._escalations:
            if esc.id == escalation_id:
                return esc
        return None

    def list_escalations(
        self,
        service: str | None = None,
        reason: EscalationReason | None = None,
        limit: int = 100,
    ) -> list[EscalationEvent]:
        """List escalations with optional filtering by service and reason."""
        results = list(self._escalations)
        if service is not None:
            results = [e for e in results if e.service == service]
        if reason is not None:
            results = [e for e in results if e.reason == reason]
        return results[-limit:]

    def resolve_escalation(self, escalation_id: str, outcome: EscalationOutcome) -> bool:
        """Set the outcome and resolved_at timestamp for an escalation."""
        for esc in self._escalations:
            if esc.id == escalation_id:
                esc.outcome = outcome
                esc.resolved_at = time.time()
                logger.info(
                    "escalation_analyzer.resolved",
                    escalation_id=escalation_id,
                    outcome=outcome,
                )
                return True
        return False

    def detect_patterns(self) -> list[EscalationPattern]:
        """Detect repeated service+reason combos occurring 3 or more times."""
        combo_counts: dict[tuple[str, str], list[EscalationEvent]] = {}
        for esc in self._escalations:
            key = (esc.service, esc.reason)
            combo_counts.setdefault(key, []).append(esc)

        patterns: list[EscalationPattern] = []
        for (service, reason), events in combo_counts.items():
            if len(events) < 3:
                continue
            resolved_times = [
                e.resolved_at - e.escalated_at for e in events if e.resolved_at is not None
            ]
            avg_time = (
                round(sum(resolved_times) / len(resolved_times), 2) if resolved_times else 0.0
            )
            patterns.append(
                EscalationPattern(
                    pattern_type=f"{service}:{reason}",
                    occurrence_count=len(events),
                    services=[service] if service else [],
                    avg_resolution_time_seconds=avg_time,
                    description=(
                        f"Repeated {reason} escalations for service '{service}' "
                        f"({len(events)} occurrences)"
                    ),
                )
            )
        return patterns

    def analyze_tier_bottlenecks(self) -> dict[str, Any]:
        """Find which to_tier has the most unresolved escalations."""
        tier_unresolved: dict[str, int] = {}
        tier_total: dict[str, int] = {}
        for esc in self._escalations:
            tier_total[esc.to_tier] = tier_total.get(esc.to_tier, 0) + 1
            if esc.outcome is None:
                tier_unresolved[esc.to_tier] = tier_unresolved.get(esc.to_tier, 0) + 1
        bottleneck = (
            max(tier_unresolved, key=tier_unresolved.get)  # type: ignore[arg-type]
            if tier_unresolved
            else ""
        )
        return {
            "tier_total": tier_total,
            "tier_unresolved": tier_unresolved,
            "bottleneck_tier": bottleneck,
        }

    def compute_false_alarm_rate(self, service: str | None = None) -> float:
        """Compute ratio of FALSE_ALARM outcomes to total resolved escalations."""
        escalations = list(self._escalations)
        if service is not None:
            escalations = [e for e in escalations if e.service == service]
        resolved = [e for e in escalations if e.outcome is not None]
        if not resolved:
            return 0.0
        false_alarms = sum(1 for e in resolved if e.outcome == EscalationOutcome.FALSE_ALARM)
        return round(false_alarms / len(resolved), 4)

    def generate_efficiency_report(self) -> EscalationEfficiencyReport:
        """Generate a comprehensive escalation efficiency report."""
        total = len(self._escalations)
        resolved = [e for e in self._escalations if e.outcome is not None]
        resolved_count = len(resolved)
        false_alarm_count = sum(1 for e in resolved if e.outcome == EscalationOutcome.FALSE_ALARM)
        false_alarm_rate = (
            round(false_alarm_count / resolved_count, 4) if resolved_count > 0 else 0.0
        )

        resolution_times = [
            e.resolved_at - e.escalated_at for e in resolved if e.resolved_at is not None
        ]
        avg_resolution = (
            round(sum(resolution_times) / len(resolution_times), 2) if resolution_times else 0.0
        )

        tier_breakdown: dict[str, int] = {}
        for esc in self._escalations:
            tier_breakdown[esc.to_tier] = tier_breakdown.get(esc.to_tier, 0) + 1

        bottleneck_info = self.analyze_tier_bottlenecks()
        bottleneck_tier = bottleneck_info.get("bottleneck_tier", "")

        recommendations: list[str] = []
        if false_alarm_rate > self._false_alarm_threshold:
            recommendations.append(
                f"False alarm rate ({false_alarm_rate:.1%}) exceeds threshold "
                f"({self._false_alarm_threshold:.1%}) — review escalation criteria."
            )
        if bottleneck_tier:
            recommendations.append(
                f"Tier {bottleneck_tier} is a bottleneck — consider adding capacity or "
                f"improving runbooks."
            )
        patterns = self.detect_patterns()
        if patterns:
            top_pattern = max(patterns, key=lambda p: p.occurrence_count)
            recommendations.append(
                f"Recurring pattern: {top_pattern.description} — automate or create playbook."
            )

        return EscalationEfficiencyReport(
            total_escalations=total,
            resolved_count=resolved_count,
            false_alarm_count=false_alarm_count,
            false_alarm_rate=false_alarm_rate,
            avg_resolution_time_seconds=avg_resolution,
            tier_breakdown=tier_breakdown,
            bottleneck_tier=bottleneck_tier,
            recommendations=recommendations,
        )

    def get_repeat_escalation_rate(self) -> float:
        """Compute ratio of incidents with multiple escalations to total unique incidents."""
        incident_counts: dict[str, int] = {}
        for esc in self._escalations:
            if esc.incident_id:
                incident_counts[esc.incident_id] = incident_counts.get(esc.incident_id, 0) + 1
        if not incident_counts:
            return 0.0
        repeat_count = sum(1 for count in incident_counts.values() if count > 1)
        return round(repeat_count / len(incident_counts), 4)

    def clear_data(self) -> None:
        """Clear all stored escalation events."""
        self._escalations.clear()
        logger.info("escalation_analyzer.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about escalation events."""
        reason_counts: dict[str, int] = {}
        outcome_counts: dict[str, int] = {}
        tier_counts: dict[str, int] = {}
        unresolved = 0
        for esc in self._escalations:
            reason_counts[esc.reason] = reason_counts.get(esc.reason, 0) + 1
            tier_counts[esc.to_tier] = tier_counts.get(esc.to_tier, 0) + 1
            if esc.outcome is not None:
                outcome_counts[esc.outcome] = outcome_counts.get(esc.outcome, 0) + 1
            else:
                unresolved += 1
        return {
            "total_escalations": len(self._escalations),
            "unresolved_count": unresolved,
            "reason_distribution": reason_counts,
            "outcome_distribution": outcome_counts,
            "tier_distribution": tier_counts,
        }
