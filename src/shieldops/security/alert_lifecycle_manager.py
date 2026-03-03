"""Alert Lifecycle Manager — track alerts through their full lifecycle phases."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AlertPhase(StrEnum):
    CREATED = "created"
    TRIAGED = "triaged"
    INVESTIGATED = "investigated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AlertPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class AlertSource(StrEnum):
    SIEM = "siem"
    EDR = "edr"
    NDR = "ndr"
    CLOUD = "cloud"
    CUSTOM = "custom"


# --- Models ---


class AlertLifecycleRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    alert_phase: AlertPhase = AlertPhase.CREATED
    alert_priority: AlertPriority = AlertPriority.MEDIUM
    alert_source: AlertSource = AlertSource.SIEM
    lifecycle_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertLifecycleAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_name: str = ""
    alert_phase: AlertPhase = AlertPhase.CREATED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertLifecycleReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertLifecycleManager:
    """Track alerts through their full lifecycle phases."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[AlertLifecycleRecord] = []
        self._analyses: list[AlertLifecycleAnalysis] = []
        logger.info(
            "alert_lifecycle_manager.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_alert(
        self,
        alert_name: str,
        alert_phase: AlertPhase = AlertPhase.CREATED,
        alert_priority: AlertPriority = AlertPriority.MEDIUM,
        alert_source: AlertSource = AlertSource.SIEM,
        lifecycle_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AlertLifecycleRecord:
        record = AlertLifecycleRecord(
            alert_name=alert_name,
            alert_phase=alert_phase,
            alert_priority=alert_priority,
            alert_source=alert_source,
            lifecycle_score=lifecycle_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_lifecycle_manager.alert_recorded",
            record_id=record.id,
            alert_name=alert_name,
            alert_phase=alert_phase.value,
            alert_priority=alert_priority.value,
        )
        return record

    def get_record(self, record_id: str) -> AlertLifecycleRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        alert_phase: AlertPhase | None = None,
        alert_priority: AlertPriority | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AlertLifecycleRecord]:
        results = list(self._records)
        if alert_phase is not None:
            results = [r for r in results if r.alert_phase == alert_phase]
        if alert_priority is not None:
            results = [r for r in results if r.alert_priority == alert_priority]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        alert_name: str,
        alert_phase: AlertPhase = AlertPhase.CREATED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AlertLifecycleAnalysis:
        analysis = AlertLifecycleAnalysis(
            alert_name=alert_name,
            alert_phase=alert_phase,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "alert_lifecycle_manager.analysis_added",
            alert_name=alert_name,
            alert_phase=alert_phase.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by alert_phase; return count and avg lifecycle_score."""
        phase_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.alert_phase.value
            phase_data.setdefault(key, []).append(r.lifecycle_score)
        result: dict[str, Any] = {}
        for phase, scores in phase_data.items():
            result[phase] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where lifecycle_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.lifecycle_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "alert_name": r.alert_name,
                        "alert_phase": r.alert_phase.value,
                        "lifecycle_score": r.lifecycle_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["lifecycle_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg lifecycle_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.lifecycle_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> AlertLifecycleReport:
        by_phase: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in self._records:
            by_phase[r.alert_phase.value] = by_phase.get(r.alert_phase.value, 0) + 1
            by_priority[r.alert_priority.value] = by_priority.get(r.alert_priority.value, 0) + 1
            by_source[r.alert_source.value] = by_source.get(r.alert_source.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.lifecycle_score < self._threshold)
        scores = [r.lifecycle_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["alert_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} alert(s) below lifecycle threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg lifecycle score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Alert lifecycle management is healthy")
        return AlertLifecycleReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_phase=by_phase,
            by_priority=by_priority,
            by_source=by_source,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("alert_lifecycle_manager.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            key = r.alert_phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "phase_distribution": phase_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
