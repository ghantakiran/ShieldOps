"""Recurrence Pattern Detector — analyze incident recurrence patterns and clusters."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RecurrenceType(StrEnum):
    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    SEASONAL = "seasonal"
    DEPLOYMENT_CORRELATED = "deployment_correlated"
    LOAD_CORRELATED = "load_correlated"


class RecurrenceFrequency(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    IRREGULAR = "irregular"


class PatternStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    EMERGING = "emerging"
    INCONCLUSIVE = "inconclusive"


# --- Models ---


class RecurrenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    service_name: str = ""
    recurrence_type: RecurrenceType = RecurrenceType.TIME_BASED
    frequency: RecurrenceFrequency = RecurrenceFrequency.IRREGULAR
    occurrence_count: int = 0
    pattern_strength: PatternStrength = PatternStrength.INCONCLUSIVE
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RecurrenceCluster(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cluster_name: str = ""
    service_name: str = ""
    incident_count: int = 0
    recurrence_type: RecurrenceType = RecurrenceType.TIME_BASED
    pattern_strength: PatternStrength = PatternStrength.INCONCLUSIVE
    created_at: float = Field(default_factory=time.time)


class RecurrencePatternReport(BaseModel):
    total_recurrences: int = 0
    total_clusters: int = 0
    avg_occurrence_count: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    strong_pattern_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RecurrencePatternDetector:
    """Analyze incident recurrence patterns and clusters."""

    def __init__(
        self,
        max_records: int = 200000,
        min_incidents: int = 3,
    ) -> None:
        self._max_records = max_records
        self._min_incidents = min_incidents
        self._records: list[RecurrenceRecord] = []
        self._clusters: list[RecurrenceCluster] = []
        logger.info(
            "recurrence_pattern.initialized",
            max_records=max_records,
            min_incidents=min_incidents,
        )

    # -- internal helpers ------------------------------------------------

    def _count_to_strength(self, count: int) -> PatternStrength:
        if count >= 10:
            return PatternStrength.STRONG
        if count >= 5:
            return PatternStrength.MODERATE
        if count >= 3:
            return PatternStrength.WEAK
        return PatternStrength.INCONCLUSIVE

    # -- record / get / list ---------------------------------------------

    def record_recurrence(
        self,
        incident_id: str,
        service_name: str,
        recurrence_type: RecurrenceType = RecurrenceType.TIME_BASED,
        frequency: RecurrenceFrequency = RecurrenceFrequency.IRREGULAR,
        occurrence_count: int = 0,
        pattern_strength: PatternStrength | None = None,
        details: str = "",
    ) -> RecurrenceRecord:
        if pattern_strength is None:
            pattern_strength = self._count_to_strength(occurrence_count)
        record = RecurrenceRecord(
            incident_id=incident_id,
            service_name=service_name,
            recurrence_type=recurrence_type,
            frequency=frequency,
            occurrence_count=occurrence_count,
            pattern_strength=pattern_strength,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "recurrence_pattern.recurrence_recorded",
            record_id=record.id,
            incident_id=incident_id,
            service_name=service_name,
            recurrence_type=recurrence_type.value,
        )
        return record

    def get_recurrence(self, record_id: str) -> RecurrenceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_recurrences(
        self,
        service_name: str | None = None,
        recurrence_type: RecurrenceType | None = None,
        limit: int = 50,
    ) -> list[RecurrenceRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if recurrence_type is not None:
            results = [r for r in results if r.recurrence_type == recurrence_type]
        return results[-limit:]

    def add_cluster(
        self,
        cluster_name: str,
        service_name: str,
        incident_count: int = 0,
        recurrence_type: RecurrenceType = RecurrenceType.TIME_BASED,
        pattern_strength: PatternStrength = PatternStrength.INCONCLUSIVE,
    ) -> RecurrenceCluster:
        cluster = RecurrenceCluster(
            cluster_name=cluster_name,
            service_name=service_name,
            incident_count=incident_count,
            recurrence_type=recurrence_type,
            pattern_strength=pattern_strength,
        )
        self._clusters.append(cluster)
        if len(self._clusters) > self._max_records:
            self._clusters = self._clusters[-self._max_records :]
        logger.info(
            "recurrence_pattern.cluster_added",
            cluster_name=cluster_name,
            service_name=service_name,
            incident_count=incident_count,
        )
        return cluster

    # -- domain operations -----------------------------------------------

    def analyze_incident_recurrence(self, service_name: str) -> dict[str, Any]:
        """Analyze recurrence for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        total_occurrences = sum(r.occurrence_count for r in records)
        avg_count = round(total_occurrences / len(records), 2)
        type_dist: dict[str, int] = {}
        for r in records:
            key = r.recurrence_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "service_name": service_name,
            "total_records": len(records),
            "total_occurrences": total_occurrences,
            "avg_occurrence_count": avg_count,
            "type_distribution": type_dist,
        }

    def identify_strong_patterns(self) -> list[dict[str, Any]]:
        """Find patterns with strength >= MODERATE."""
        strong = {PatternStrength.STRONG, PatternStrength.MODERATE}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.pattern_strength in strong:
                results.append(
                    {
                        "incident_id": r.incident_id,
                        "service_name": r.service_name,
                        "recurrence_type": r.recurrence_type.value,
                        "occurrence_count": r.occurrence_count,
                        "pattern_strength": r.pattern_strength.value,
                    }
                )
        results.sort(key=lambda x: x["occurrence_count"], reverse=True)
        return results

    def rank_by_incident_count(self) -> list[dict[str, Any]]:
        """Rank by occurrence_count descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "incident_id": r.incident_id,
                    "service_name": r.service_name,
                    "occurrence_count": r.occurrence_count,
                    "pattern_strength": r.pattern_strength.value,
                    "frequency": r.frequency.value,
                }
            )
        results.sort(key=lambda x: x["occurrence_count"], reverse=True)
        return results

    def detect_emerging_patterns(self) -> list[dict[str, Any]]:
        """Find EMERGING patterns."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.pattern_strength == PatternStrength.EMERGING:
                results.append(
                    {
                        "incident_id": r.incident_id,
                        "service_name": r.service_name,
                        "recurrence_type": r.recurrence_type.value,
                        "frequency": r.frequency.value,
                        "occurrence_count": r.occurrence_count,
                    }
                )
        results.sort(key=lambda x: x["occurrence_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> RecurrencePatternReport:
        by_type: dict[str, int] = {}
        by_frequency: dict[str, int] = {}
        for r in self._records:
            by_type[r.recurrence_type.value] = by_type.get(r.recurrence_type.value, 0) + 1
            by_frequency[r.frequency.value] = by_frequency.get(r.frequency.value, 0) + 1
        avg_count = (
            round(
                sum(r.occurrence_count for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        strong_count = sum(
            1
            for r in self._records
            if r.pattern_strength in (PatternStrength.STRONG, PatternStrength.MODERATE)
        )
        recs: list[str] = []
        if strong_count > 0:
            recs.append(f"{strong_count} strong/moderate recurrence pattern(s) detected")
        emerging = sum(1 for r in self._records if r.pattern_strength == PatternStrength.EMERGING)
        if emerging > 0:
            recs.append(f"{emerging} emerging pattern(s) require monitoring")
        if not recs:
            recs.append("No significant recurrence patterns detected")
        return RecurrencePatternReport(
            total_recurrences=len(self._records),
            total_clusters=len(self._clusters),
            avg_occurrence_count=avg_count,
            by_type=by_type,
            by_frequency=by_frequency,
            strong_pattern_count=strong_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._clusters.clear()
        logger.info("recurrence_pattern.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.recurrence_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_recurrences": len(self._records),
            "total_clusters": len(self._clusters),
            "min_incidents": self._min_incidents,
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
