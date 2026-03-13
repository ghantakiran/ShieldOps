"""Incident Recurrence Pattern Engine — compute recurrence frequency,
detect systemic patterns, rank recurrence clusters."""

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
    EXACT = "exact"
    SIMILAR = "similar"
    RELATED = "related"
    SEASONAL = "seasonal"


class PatternScope(StrEnum):
    SERVICE = "service"
    TEAM = "team"
    INFRASTRUCTURE = "infrastructure"
    ORGANIZATION = "organization"


class RecurrenceRisk(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class RecurrencePatternRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    recurrence_type: RecurrenceType = RecurrenceType.SIMILAR
    pattern_scope: PatternScope = PatternScope.SERVICE
    recurrence_risk: RecurrenceRisk = RecurrenceRisk.MEDIUM
    occurrence_count: int = 1
    pattern_signature: str = ""
    service: str = ""
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RecurrencePatternAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    recurrence_type: RecurrenceType = RecurrenceType.SIMILAR
    frequency_score: float = 0.0
    is_systemic: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RecurrencePatternReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_occurrence_count: float = 0.0
    by_recurrence_type: dict[str, int] = Field(default_factory=dict)
    by_pattern_scope: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentRecurrencePatternEngine:
    """Compute recurrence frequency, detect systemic patterns,
    rank recurrence clusters."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RecurrencePatternRecord] = []
        self._analyses: dict[str, RecurrencePatternAnalysis] = {}
        logger.info(
            "incident_recurrence_pattern_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        incident_id: str = "",
        recurrence_type: RecurrenceType = RecurrenceType.SIMILAR,
        pattern_scope: PatternScope = PatternScope.SERVICE,
        recurrence_risk: RecurrenceRisk = RecurrenceRisk.MEDIUM,
        occurrence_count: int = 1,
        pattern_signature: str = "",
        service: str = "",
        team: str = "",
        description: str = "",
    ) -> RecurrencePatternRecord:
        record = RecurrencePatternRecord(
            incident_id=incident_id,
            recurrence_type=recurrence_type,
            pattern_scope=pattern_scope,
            recurrence_risk=recurrence_risk,
            occurrence_count=occurrence_count,
            pattern_signature=pattern_signature,
            service=service,
            team=team,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_recurrence_pattern.record_added",
            record_id=record.id,
            incident_id=incident_id,
        )
        return record

    def process(self, key: str) -> RecurrencePatternAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        sig_count = sum(1 for r in self._records if r.pattern_signature == rec.pattern_signature)
        is_systemic = sig_count > 2 or rec.recurrence_risk in (
            RecurrenceRisk.CRITICAL,
            RecurrenceRisk.HIGH,
        )
        analysis = RecurrencePatternAnalysis(
            incident_id=rec.incident_id,
            recurrence_type=rec.recurrence_type,
            frequency_score=round(rec.occurrence_count * sig_count, 2),
            is_systemic=is_systemic,
            description=f"Incident {rec.incident_id} recurrence pattern {rec.pattern_signature}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RecurrencePatternReport:
        by_rt: dict[str, int] = {}
        by_ps: dict[str, int] = {}
        by_rk: dict[str, int] = {}
        counts: list[int] = []
        for r in self._records:
            by_rt[r.recurrence_type.value] = by_rt.get(r.recurrence_type.value, 0) + 1
            by_ps[r.pattern_scope.value] = by_ps.get(r.pattern_scope.value, 0) + 1
            by_rk[r.recurrence_risk.value] = by_rk.get(r.recurrence_risk.value, 0) + 1
            counts.append(r.occurrence_count)
        avg = round(sum(counts) / len(counts), 2) if counts else 0.0
        recs: list[str] = []
        critical = by_rk.get("critical", 0)
        if critical > 0:
            recs.append(f"{critical} critical recurrence patterns need investigation")
        if not recs:
            recs.append("No critical recurrence patterns detected")
        return RecurrencePatternReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_occurrence_count=avg,
            by_recurrence_type=by_rt,
            by_pattern_scope=by_ps,
            by_risk=by_rk,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            k = r.recurrence_type.value
            type_dist[k] = type_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "recurrence_type_distribution": type_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("incident_recurrence_pattern_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_recurrence_frequency(self) -> list[dict[str, Any]]:
        """Compute recurrence frequency per pattern signature."""
        sig_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            k = r.pattern_signature
            if k not in sig_data:
                sig_data[k] = {"count": 0, "total_occurrences": 0, "incidents": set()}
            sig_data[k]["count"] += 1
            sig_data[k]["total_occurrences"] += r.occurrence_count
            sig_data[k]["incidents"].add(r.incident_id)
        results: list[dict[str, Any]] = []
        for sig, data in sig_data.items():
            results.append(
                {
                    "pattern_signature": sig,
                    "record_count": data["count"],
                    "total_occurrences": data["total_occurrences"],
                    "unique_incidents": len(data["incidents"]),
                }
            )
        results.sort(key=lambda x: x["total_occurrences"], reverse=True)
        return results

    def detect_systemic_patterns(self) -> list[dict[str, Any]]:
        """Detect systemic patterns affecting multiple services/teams."""
        scope_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            k = r.pattern_scope.value
            if k not in scope_data:
                scope_data[k] = {"count": 0, "services": set(), "teams": set()}
            scope_data[k]["count"] += 1
            scope_data[k]["services"].add(r.service)
            scope_data[k]["teams"].add(r.team)
        results: list[dict[str, Any]] = []
        for scope, data in scope_data.items():
            if data["count"] > 1:
                results.append(
                    {
                        "scope": scope,
                        "pattern_count": data["count"],
                        "unique_services": len(data["services"]),
                        "unique_teams": len(data["teams"]),
                    }
                )
        results.sort(key=lambda x: x["pattern_count"], reverse=True)
        return results

    def rank_recurrence_clusters(self) -> list[dict[str, Any]]:
        """Rank pattern clusters by total recurrence impact."""
        cluster_data: dict[str, float] = {}
        cluster_risks: dict[str, str] = {}
        for r in self._records:
            cluster_data[r.pattern_signature] = (
                cluster_data.get(r.pattern_signature, 0.0) + r.occurrence_count
            )
            cluster_risks[r.pattern_signature] = r.recurrence_risk.value
        results: list[dict[str, Any]] = []
        for sig, total in cluster_data.items():
            results.append(
                {
                    "pattern_signature": sig,
                    "risk_level": cluster_risks[sig],
                    "total_occurrences": total,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["total_occurrences"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
