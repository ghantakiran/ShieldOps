"""Event Pattern Discovery Engine

Discovers recurring event sequences and temporal patterns
to enable early warning and proactive incident prevention.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PatternFrequency(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    IRREGULAR = "irregular"


class PatternConfidence(StrEnum):
    CONFIRMED = "confirmed"
    PROBABLE = "probable"
    SUSPECTED = "suspected"
    UNVERIFIED = "unverified"


class EventCategory(StrEnum):
    DEPLOYMENT = "deployment"
    ALERT = "alert"
    SCALING = "scaling"
    FAILURE = "failure"
    CONFIG_CHANGE = "config_change"
    TRAFFIC_SHIFT = "traffic_shift"


# --- Models ---


class EventPatternRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    event_sequence: str = ""
    frequency: PatternFrequency = PatternFrequency.IRREGULAR
    confidence: PatternConfidence = PatternConfidence.UNVERIFIED
    first_seen_at: float = 0.0
    occurrence_count: int = 0
    services_involved: int = 0
    lead_time_minutes: float = 0.0
    created_at: float = Field(default_factory=time.time)


class EventPatternAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EventPatternReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    confirmed_patterns: int = 0
    avg_lead_time_minutes: float = 0.0
    by_frequency: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EventPatternDiscoveryEngine:
    """Event Pattern Discovery Engine

    Discovers recurring event sequences and temporal
    patterns for early warning systems.
    """

    def __init__(
        self,
        max_records: int = 200000,
        min_occurrences: int = 3,
    ) -> None:
        self._max_records = max_records
        self._min_occurrences = min_occurrences
        self._records: list[EventPatternRecord] = []
        self._analyses: list[EventPatternAnalysis] = []
        logger.info(
            "event_pattern_discovery_engine.initialized",
            max_records=max_records,
            min_occurrences=min_occurrences,
        )

    def add_record(
        self,
        pattern_id: str,
        event_sequence: str,
        frequency: PatternFrequency = (PatternFrequency.IRREGULAR),
        confidence: PatternConfidence = (PatternConfidence.UNVERIFIED),
        first_seen_at: float = 0.0,
        occurrence_count: int = 0,
        services_involved: int = 0,
        lead_time_minutes: float = 0.0,
    ) -> EventPatternRecord:
        record = EventPatternRecord(
            pattern_id=pattern_id,
            event_sequence=event_sequence,
            frequency=frequency,
            confidence=confidence,
            first_seen_at=first_seen_at,
            occurrence_count=occurrence_count,
            services_involved=services_involved,
            lead_time_minutes=lead_time_minutes,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "event_pattern_discovery_engine.record_added",
            record_id=record.id,
            pattern_id=pattern_id,
        )
        return record

    def discover_sequences(self, min_count: int | None = None) -> list[dict[str, Any]]:
        threshold = min_count if min_count is not None else self._min_occurrences
        seq_counts: dict[str, int] = {}
        for r in self._records:
            seq = r.event_sequence
            seq_counts[seq] = seq_counts.get(seq, 0) + r.occurrence_count
        results = []
        for seq, count in seq_counts.items():
            if count >= threshold:
                results.append({"sequence": seq, "total_count": count})
        return sorted(
            results,
            key=lambda x: x["total_count"],
            reverse=True,
        )

    def compute_pattern_frequency(self, pattern_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.pattern_id == pattern_id]
        if not matching:
            return {
                "pattern_id": pattern_id,
                "status": "no_data",
            }
        freq_counts: dict[str, int] = {}
        for r in matching:
            fv = r.frequency.value
            freq_counts[fv] = freq_counts.get(fv, 0) + 1
        dominant = max(
            freq_counts,
            key=freq_counts.get,  # type: ignore[arg-type]
        )
        total_occ = sum(r.occurrence_count for r in matching)
        return {
            "pattern_id": pattern_id,
            "dominant_frequency": dominant,
            "total_occurrences": total_occ,
            "frequency_distribution": freq_counts,
        }

    def identify_early_warnings(
        self,
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.pattern_id in seen:
                continue
            if (
                r.confidence
                in (
                    PatternConfidence.CONFIRMED,
                    PatternConfidence.PROBABLE,
                )
                and r.lead_time_minutes > 0
                and r.occurrence_count >= self._min_occurrences
            ):
                warnings.append(
                    {
                        "pattern_id": r.pattern_id,
                        "sequence": r.event_sequence,
                        "lead_time_min": (r.lead_time_minutes),
                        "occurrences": r.occurrence_count,
                        "confidence": r.confidence.value,
                    }
                )
                seen.add(r.pattern_id)
        return sorted(
            warnings,
            key=lambda x: x["lead_time_min"],
            reverse=True,
        )

    def process(self, pattern_id: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.pattern_id == pattern_id]
        if not matching:
            return {
                "pattern_id": pattern_id,
                "status": "no_data",
            }
        total_occ = sum(r.occurrence_count for r in matching)
        lead_times = [r.lead_time_minutes for r in matching if r.lead_time_minutes > 0]
        avg_lead = round(sum(lead_times) / len(lead_times), 2) if lead_times else 0.0
        confirmed = sum(1 for r in matching if r.confidence == PatternConfidence.CONFIRMED)
        return {
            "pattern_id": pattern_id,
            "record_count": len(matching),
            "total_occurrences": total_occ,
            "avg_lead_time_minutes": avg_lead,
            "confirmed_records": confirmed,
        }

    def generate_report(self) -> EventPatternReport:
        by_freq: dict[str, int] = {}
        by_conf: dict[str, int] = {}
        for r in self._records:
            fv = r.frequency.value
            by_freq[fv] = by_freq.get(fv, 0) + 1
            cv = r.confidence.value
            by_conf[cv] = by_conf.get(cv, 0) + 1
        confirmed = by_conf.get("confirmed", 0)
        lead_times = [r.lead_time_minutes for r in self._records if r.lead_time_minutes > 0]
        avg_lead = round(sum(lead_times) / len(lead_times), 2) if lead_times else 0.0
        recs: list[str] = []
        unverified = by_conf.get("unverified", 0)
        total = len(self._records)
        if total > 0 and unverified / total > 0.5:
            recs.append("Over 50% patterns unverified — label feedback needed")
        if avg_lead > 0 and confirmed > 0:
            recs.append(f"{confirmed} confirmed pattern(s) with {avg_lead:.0f}min lead time")
        if not recs:
            recs.append("Event pattern discovery is nominal")
        return EventPatternReport(
            total_records=total,
            total_analyses=len(self._analyses),
            confirmed_patterns=confirmed,
            avg_lead_time_minutes=avg_lead,
            by_frequency=by_freq,
            by_confidence=by_conf,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        conf_dist: dict[str, int] = {}
        for r in self._records:
            k = r.confidence.value
            conf_dist[k] = conf_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "min_occurrences": self._min_occurrences,
            "confidence_distribution": conf_dist,
            "unique_patterns": len({r.pattern_id for r in self._records}),
            "unique_sequences": len({r.event_sequence for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("event_pattern_discovery_engine.cleared")
        return {"status": "cleared"}
