"""Timeline Correlator — correlate incident events across timelines."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EventType(StrEnum):
    ALERT_FIRED = "alert_fired"
    DEPLOYMENT = "deployment"
    CONFIG_CHANGE = "config_change"
    SCALING_EVENT = "scaling_event"
    HUMAN_ACTION = "human_action"


class CorrelationStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    COINCIDENTAL = "coincidental"
    NONE = "none"


class TimelinePhase(StrEnum):
    DETECTION = "detection"
    TRIAGE = "triage"
    INVESTIGATION = "investigation"
    REMEDIATION = "remediation"
    RECOVERY = "recovery"


# --- Models ---


class CorrelationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_name: str = ""
    event_type: EventType = EventType.ALERT_FIRED
    strength: CorrelationStrength = CorrelationStrength.MODERATE
    phase: TimelinePhase = TimelinePhase.DETECTION
    confidence_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CorrelationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    event_type: EventType = EventType.ALERT_FIRED
    phase: TimelinePhase = TimelinePhase.DETECTION
    min_confidence_pct: float = 60.0
    time_window_minutes: float = 30.0
    created_at: float = Field(default_factory=time.time)


class TimelineCorrelatorReport(BaseModel):
    total_correlations: int = 0
    total_rules: int = 0
    strong_rate_pct: float = 0.0
    by_event_type: dict[str, int] = Field(default_factory=dict)
    by_strength: dict[str, int] = Field(default_factory=dict)
    weak_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentTimelineCorrelator:
    """Correlate incident events across timelines."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_pct: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_pct = min_confidence_pct
        self._records: list[CorrelationRecord] = []
        self._policies: list[CorrelationRule] = []
        logger.info(
            "timeline_correlator.initialized",
            max_records=max_records,
            min_confidence_pct=min_confidence_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_correlation(
        self,
        incident_name: str,
        event_type: EventType = EventType.ALERT_FIRED,
        strength: CorrelationStrength = (CorrelationStrength.MODERATE),
        phase: TimelinePhase = TimelinePhase.DETECTION,
        confidence_pct: float = 0.0,
        details: str = "",
    ) -> CorrelationRecord:
        record = CorrelationRecord(
            incident_name=incident_name,
            event_type=event_type,
            strength=strength,
            phase=phase,
            confidence_pct=confidence_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "timeline_correlator.recorded",
            record_id=record.id,
            incident_name=incident_name,
            event_type=event_type.value,
            strength=strength.value,
        )
        return record

    def get_correlation(self, record_id: str) -> CorrelationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_correlations(
        self,
        incident_name: str | None = None,
        event_type: EventType | None = None,
        limit: int = 50,
    ) -> list[CorrelationRecord]:
        results = list(self._records)
        if incident_name is not None:
            results = [r for r in results if r.incident_name == incident_name]
        if event_type is not None:
            results = [r for r in results if r.event_type == event_type]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        event_type: EventType = EventType.ALERT_FIRED,
        phase: TimelinePhase = TimelinePhase.DETECTION,
        min_confidence_pct: float = 60.0,
        time_window_minutes: float = 30.0,
    ) -> CorrelationRule:
        rule = CorrelationRule(
            rule_name=rule_name,
            event_type=event_type,
            phase=phase,
            min_confidence_pct=min_confidence_pct,
            time_window_minutes=time_window_minutes,
        )
        self._policies.append(rule)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "timeline_correlator.rule_added",
            rule_name=rule_name,
            event_type=event_type.value,
            phase=phase.value,
        )
        return rule

    # -- domain operations -------------------------------------------

    def analyze_correlation_quality(self, incident_name: str) -> dict[str, Any]:
        """Analyze correlation quality for incident."""
        records = [r for r in self._records if r.incident_name == incident_name]
        if not records:
            return {
                "incident_name": incident_name,
                "status": "no_data",
            }
        strong_count = sum(
            1
            for r in records
            if r.strength
            in (
                CorrelationStrength.STRONG,
                CorrelationStrength.MODERATE,
            )
        )
        strong_rate = round(strong_count / len(records) * 100, 2)
        avg_confidence = round(
            sum(r.confidence_pct for r in records) / len(records),
            2,
        )
        return {
            "incident_name": incident_name,
            "correlation_count": len(records),
            "strong_count": strong_count,
            "strong_rate": strong_rate,
            "avg_confidence": avg_confidence,
            "meets_threshold": (avg_confidence >= self._min_confidence_pct),
        }

    def identify_weak_correlations(
        self,
    ) -> list[dict[str, Any]]:
        """Find incidents with repeated weak correlations."""
        weak_counts: dict[str, int] = {}
        for r in self._records:
            if r.strength in (
                CorrelationStrength.WEAK,
                CorrelationStrength.COINCIDENTAL,
            ):
                weak_counts[r.incident_name] = weak_counts.get(r.incident_name, 0) + 1
        results: list[dict[str, Any]] = []
        for incident, count in weak_counts.items():
            if count > 1:
                results.append(
                    {
                        "incident_name": incident,
                        "weak_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["weak_count"],
            reverse=True,
        )
        return results

    def rank_by_confidence(
        self,
    ) -> list[dict[str, Any]]:
        """Rank incidents by avg confidence desc."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self._records:
            totals[r.incident_name] = totals.get(r.incident_name, 0.0) + r.confidence_pct
            counts[r.incident_name] = counts.get(r.incident_name, 0) + 1
        results: list[dict[str, Any]] = []
        for incident, total in totals.items():
            avg = round(total / counts[incident], 2)
            results.append(
                {
                    "incident_name": incident,
                    "avg_confidence_pct": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_confidence_pct"],
            reverse=True,
        )
        return results

    def detect_correlation_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Detect incidents with >3 non-STRONG/MODERATE."""
        non_strong: dict[str, int] = {}
        for r in self._records:
            if r.strength not in (
                CorrelationStrength.STRONG,
                CorrelationStrength.MODERATE,
            ):
                non_strong[r.incident_name] = non_strong.get(r.incident_name, 0) + 1
        results: list[dict[str, Any]] = []
        for incident, count in non_strong.items():
            if count > 3:
                results.append(
                    {
                        "incident_name": incident,
                        "non_strong_count": count,
                        "gap_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_strong_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(
        self,
    ) -> TimelineCorrelatorReport:
        by_event_type: dict[str, int] = {}
        by_strength: dict[str, int] = {}
        for r in self._records:
            by_event_type[r.event_type.value] = by_event_type.get(r.event_type.value, 0) + 1
            by_strength[r.strength.value] = by_strength.get(r.strength.value, 0) + 1
        strong_count = sum(
            1
            for r in self._records
            if r.strength
            in (
                CorrelationStrength.STRONG,
                CorrelationStrength.MODERATE,
            )
        )
        strong_rate = (
            round(
                strong_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        weak = sum(1 for d in self.identify_weak_correlations())
        recs: list[str] = []
        if strong_rate < 100.0 and self._records:
            recs.append(f"Strong rate {strong_rate}% is below 100% threshold")
        if weak > 0:
            recs.append(f"{weak} incident(s) with weak correlations")
        gaps = len(self.detect_correlation_gaps())
        if gaps > 0:
            recs.append(f"{gaps} incident(s) with correlation gaps detected")
        if not recs:
            recs.append("Correlation quality is optimal across all incidents")
        return TimelineCorrelatorReport(
            total_correlations=len(self._records),
            total_rules=len(self._policies),
            strong_rate_pct=strong_rate,
            by_event_type=by_event_type,
            by_strength=by_strength,
            weak_count=weak,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("timeline_correlator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        event_dist: dict[str, int] = {}
        for r in self._records:
            key = r.event_type.value
            event_dist[key] = event_dist.get(key, 0) + 1
        return {
            "total_correlations": len(self._records),
            "total_rules": len(self._policies),
            "min_confidence_pct": (self._min_confidence_pct),
            "event_type_distribution": event_dist,
            "unique_incidents": len({r.incident_name for r in self._records}),
        }
