"""Incident Lifecycle State Engine — track incident phases,
compute dwell times, detect bottlenecks, rank by resolution velocity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IncidentPhase(StrEnum):
    DETECTED = "detected"
    TRIAGED = "triaged"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TrackingMode(StrEnum):
    REALTIME = "realtime"
    BATCH = "batch"
    SNAPSHOT = "snapshot"


# --- Models ---


class LifecycleStateRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    phase: IncidentPhase = IncidentPhase.DETECTED
    severity: Severity = Severity.MEDIUM
    tracking_mode: TrackingMode = TrackingMode.REALTIME
    dwell_time_seconds: float = 0.0
    service: str = ""
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LifecycleStateAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    phase: IncidentPhase = IncidentPhase.DETECTED
    avg_dwell_time: float = 0.0
    is_bottleneck: bool = False
    resolution_velocity: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LifecycleStateReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_dwell_time: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_tracking_mode: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentLifecycleStateEngine:
    """Track incident lifecycle phases, compute dwell times,
    detect bottlenecks, rank by resolution velocity."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[LifecycleStateRecord] = []
        self._analyses: dict[str, LifecycleStateAnalysis] = {}
        logger.info(
            "incident_lifecycle_state_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        incident_id: str = "",
        phase: IncidentPhase = IncidentPhase.DETECTED,
        severity: Severity = Severity.MEDIUM,
        tracking_mode: TrackingMode = TrackingMode.REALTIME,
        dwell_time_seconds: float = 0.0,
        service: str = "",
        team: str = "",
        description: str = "",
    ) -> LifecycleStateRecord:
        record = LifecycleStateRecord(
            incident_id=incident_id,
            phase=phase,
            severity=severity,
            tracking_mode=tracking_mode,
            dwell_time_seconds=dwell_time_seconds,
            service=service,
            team=team,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_lifecycle_state.record_added",
            record_id=record.id,
            incident_id=incident_id,
        )
        return record

    def process(self, key: str) -> LifecycleStateAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.incident_id == rec.incident_id]
        avg_dwell = (
            round(sum(r.dwell_time_seconds for r in related) / len(related), 2) if related else 0.0
        )
        is_bottleneck = rec.dwell_time_seconds > avg_dwell * 1.5
        total_dwell = sum(r.dwell_time_seconds for r in related)
        velocity = round(1.0 / total_dwell, 4) if total_dwell > 0 else 0.0
        analysis = LifecycleStateAnalysis(
            incident_id=rec.incident_id,
            phase=rec.phase,
            avg_dwell_time=avg_dwell,
            is_bottleneck=is_bottleneck,
            resolution_velocity=velocity,
            description=f"Incident {rec.incident_id} phase {rec.phase.value}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> LifecycleStateReport:
        by_phase: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_mode: dict[str, int] = {}
        dwells: list[float] = []
        for r in self._records:
            by_phase[r.phase.value] = by_phase.get(r.phase.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
            by_mode[r.tracking_mode.value] = by_mode.get(r.tracking_mode.value, 0) + 1
            dwells.append(r.dwell_time_seconds)
        avg = round(sum(dwells) / len(dwells), 2) if dwells else 0.0
        recs: list[str] = []
        if avg > 300:
            recs.append("Average dwell time exceeds 5 minutes — investigate bottlenecks")
        if not recs:
            recs.append("No significant lifecycle issues detected")
        return LifecycleStateReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_dwell_time=avg,
            by_phase=by_phase,
            by_severity=by_severity,
            by_tracking_mode=by_mode,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            k = r.phase.value
            phase_dist[k] = phase_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "phase_distribution": phase_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("incident_lifecycle_state_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_phase_dwell_times(self) -> list[dict[str, Any]]:
        """Compute average dwell time per phase."""
        phase_dwells: dict[str, list[float]] = {}
        for r in self._records:
            phase_dwells.setdefault(r.phase.value, []).append(r.dwell_time_seconds)
        results: list[dict[str, Any]] = []
        for phase, dwells in phase_dwells.items():
            avg = round(sum(dwells) / len(dwells), 2)
            results.append(
                {
                    "phase": phase,
                    "avg_dwell_seconds": avg,
                    "max_dwell_seconds": round(max(dwells), 2),
                    "count": len(dwells),
                }
            )
        results.sort(key=lambda x: x["avg_dwell_seconds"], reverse=True)
        return results

    def detect_lifecycle_bottlenecks(self) -> list[dict[str, Any]]:
        """Detect phases where dwell time exceeds threshold."""
        phase_dwells: dict[str, list[float]] = {}
        for r in self._records:
            phase_dwells.setdefault(r.phase.value, []).append(r.dwell_time_seconds)
        overall_avg = (
            sum(r.dwell_time_seconds for r in self._records) / len(self._records)
            if self._records
            else 0.0
        )
        results: list[dict[str, Any]] = []
        for phase, dwells in phase_dwells.items():
            avg = sum(dwells) / len(dwells)
            if avg > overall_avg * 1.5:
                results.append(
                    {
                        "phase": phase,
                        "avg_dwell_seconds": round(avg, 2),
                        "overall_avg": round(overall_avg, 2),
                        "ratio": round(avg / overall_avg, 2) if overall_avg > 0 else 0.0,
                    }
                )
        results.sort(key=lambda x: x["ratio"], reverse=True)
        return results

    def rank_incidents_by_resolution_velocity(self) -> list[dict[str, Any]]:
        """Rank incidents by total resolution time (lower is faster)."""
        incident_dwell: dict[str, float] = {}
        incident_sev: dict[str, str] = {}
        for r in self._records:
            incident_dwell[r.incident_id] = (
                incident_dwell.get(r.incident_id, 0.0) + r.dwell_time_seconds
            )
            incident_sev[r.incident_id] = r.severity.value
        results: list[dict[str, Any]] = []
        for iid, total in incident_dwell.items():
            velocity = round(1.0 / total, 4) if total > 0 else 0.0
            results.append(
                {
                    "incident_id": iid,
                    "severity": incident_sev[iid],
                    "total_dwell_seconds": round(total, 2),
                    "resolution_velocity": velocity,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["resolution_velocity"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
