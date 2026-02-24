"""Incident Timeline Analyzer — response pattern bottlenecks across phases."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TimelinePhase(StrEnum):
    DETECTION = "detection"
    TRIAGE = "triage"
    INVESTIGATION = "investigation"
    MITIGATION = "mitigation"
    RESOLUTION = "resolution"


class BottleneckType(StrEnum):
    SLOW_DETECTION = "slow_detection"
    DELAYED_TRIAGE = "delayed_triage"
    LONG_INVESTIGATION = "long_investigation"
    FAILED_MITIGATION = "failed_mitigation"
    EXTENDED_RESOLUTION = "extended_resolution"


class ResponseQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    BELOW_TARGET = "below_target"
    CRITICAL = "critical"


# --- Models ---


class TimelineEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    phase: TimelinePhase = TimelinePhase.DETECTION
    started_at: float = Field(default_factory=time.time)
    ended_at: float = 0.0
    duration_minutes: float = 0.0
    assignee: str = ""
    notes: str = ""
    created_at: float = Field(default_factory=time.time)


class BottleneckAnalysis(BaseModel):
    incident_id: str = ""
    bottleneck_type: BottleneckType = BottleneckType.SLOW_DETECTION
    phase: TimelinePhase = TimelinePhase.DETECTION
    duration_minutes: float = 0.0
    target_minutes: float = 0.0
    overshoot_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class TimelineReport(BaseModel):
    total_incidents: int = 0
    total_entries: int = 0
    avg_resolution_minutes: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    bottlenecks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---

_DEFAULT_TARGETS: dict[TimelinePhase, float] = {
    TimelinePhase.DETECTION: 5.0,
    TimelinePhase.TRIAGE: 10.0,
    TimelinePhase.INVESTIGATION: 30.0,
    TimelinePhase.MITIGATION: 15.0,
    TimelinePhase.RESOLUTION: 60.0,
}

_PHASE_TO_BOTTLENECK: dict[TimelinePhase, BottleneckType] = {
    TimelinePhase.DETECTION: BottleneckType.SLOW_DETECTION,
    TimelinePhase.TRIAGE: BottleneckType.DELAYED_TRIAGE,
    TimelinePhase.INVESTIGATION: BottleneckType.LONG_INVESTIGATION,
    TimelinePhase.MITIGATION: BottleneckType.FAILED_MITIGATION,
    TimelinePhase.RESOLUTION: BottleneckType.EXTENDED_RESOLUTION,
}


class IncidentTimelineAnalyzer:
    """Analyze incident timelines to identify response
    pattern bottlenecks (detection -> resolution)."""

    def __init__(
        self,
        max_entries: int = 200000,
        target_resolution_minutes: float = 60,
    ) -> None:
        self._max_entries = max_entries
        self._target_resolution_minutes = target_resolution_minutes
        self._items: list[TimelineEntry] = []
        self._bottlenecks: dict[str, list[BottleneckAnalysis]] = {}
        logger.info(
            "incident_timeline.initialized",
            max_entries=max_entries,
            target_resolution_minutes=target_resolution_minutes,
        )

    # -- CRUD -------------------------------------------------------

    def record_phase(
        self,
        incident_id: str,
        phase: TimelinePhase = TimelinePhase.DETECTION,
        started_at: float | None = None,
        ended_at: float = 0.0,
        duration_minutes: float = 0.0,
        assignee: str = "",
        notes: str = "",
        **kw: Any,
    ) -> TimelineEntry:
        """Record a phase entry for an incident."""
        entry = TimelineEntry(
            incident_id=incident_id,
            phase=phase,
            started_at=started_at or time.time(),
            ended_at=ended_at,
            duration_minutes=duration_minutes,
            assignee=assignee,
            notes=notes,
            **kw,
        )
        self._items.append(entry)
        if len(self._items) > self._max_entries:
            self._items = self._items[-self._max_entries :]
        logger.info(
            "incident_timeline.phase_recorded",
            entry_id=entry.id,
            incident_id=incident_id,
            phase=phase,
        )
        return entry

    def get_entry(
        self,
        entry_id: str,
    ) -> TimelineEntry | None:
        """Retrieve a timeline entry by ID."""
        for item in self._items:
            if item.id == entry_id:
                return item
        return None

    def list_entries(
        self,
        incident_id: str | None = None,
        phase: TimelinePhase | None = None,
        limit: int = 50,
    ) -> list[TimelineEntry]:
        """List entries with optional filters."""
        results = list(self._items)
        if incident_id is not None:
            results = [e for e in results if e.incident_id == incident_id]
        if phase is not None:
            results = [e for e in results if e.phase == phase]
        return results[-limit:]

    # -- Domain operations ------------------------------------------

    def calculate_phase_durations(
        self,
        incident_id: str,
    ) -> dict[str, float]:
        """Calculate total duration per phase for an incident."""
        entries = [e for e in self._items if e.incident_id == incident_id]
        durations: dict[str, float] = {}
        for e in entries:
            key = e.phase.value
            durations[key] = durations.get(key, 0) + e.duration_minutes
        return durations

    def detect_bottlenecks(
        self,
        incident_id: str,
        targets: dict[TimelinePhase, float] | None = None,
    ) -> list[BottleneckAnalysis]:
        """Detect bottlenecks for an incident against targets."""
        tgts = targets or _DEFAULT_TARGETS
        durations = self.calculate_phase_durations(incident_id)
        bottlenecks: list[BottleneckAnalysis] = []
        for phase, target in tgts.items():
            actual = durations.get(phase.value, 0.0)
            if actual > target and target > 0:
                overshoot = round(
                    (actual - target) / target * 100,
                    2,
                )
                bn = BottleneckAnalysis(
                    incident_id=incident_id,
                    bottleneck_type=_PHASE_TO_BOTTLENECK.get(
                        phase,
                        BottleneckType.SLOW_DETECTION,
                    ),
                    phase=phase,
                    duration_minutes=actual,
                    target_minutes=target,
                    overshoot_pct=overshoot,
                )
                bottlenecks.append(bn)
        self._bottlenecks[incident_id] = bottlenecks
        logger.info(
            "incident_timeline.bottlenecks_detected",
            incident_id=incident_id,
            count=len(bottlenecks),
        )
        return bottlenecks

    def analyze_response_quality(
        self,
        incident_id: str,
    ) -> ResponseQuality:
        """Analyze overall response quality for an incident."""
        durations = self.calculate_phase_durations(incident_id)
        total = sum(durations.values())
        target = self._target_resolution_minutes
        if target <= 0:
            return ResponseQuality.ACCEPTABLE
        ratio = total / target
        if ratio <= 0.5:
            return ResponseQuality.EXCELLENT
        if ratio <= 1.0:
            return ResponseQuality.GOOD
        if ratio <= 1.5:
            return ResponseQuality.ACCEPTABLE
        if ratio <= 3.0:
            return ResponseQuality.BELOW_TARGET
        return ResponseQuality.CRITICAL

    def compare_incident_timelines(
        self,
        incident_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Compare timelines across multiple incidents."""
        comparisons: list[dict[str, Any]] = []
        for iid in incident_ids:
            durations = self.calculate_phase_durations(iid)
            total = sum(durations.values())
            quality = self.analyze_response_quality(iid)
            comparisons.append(
                {
                    "incident_id": iid,
                    "total_minutes": round(total, 2),
                    "phase_durations": durations,
                    "quality": quality.value,
                }
            )
        comparisons.sort(key=lambda c: c["total_minutes"])
        return comparisons

    def identify_improvement_areas(
        self,
    ) -> list[dict[str, Any]]:
        """Identify phases that consistently exceed targets."""
        phase_totals: dict[str, list[float]] = {}
        for e in self._items:
            key = e.phase.value
            phase_totals.setdefault(key, []).append(
                e.duration_minutes,
            )
        areas: list[dict[str, Any]] = []
        for phase_val, durations in phase_totals.items():
            avg = (
                round(
                    sum(durations) / len(durations),
                    2,
                )
                if durations
                else 0.0
            )
            phase_enum = TimelinePhase(phase_val)
            target = _DEFAULT_TARGETS.get(phase_enum, 0.0)
            if avg > target and target > 0:
                areas.append(
                    {
                        "phase": phase_val,
                        "avg_duration_minutes": avg,
                        "target_minutes": target,
                        "overshoot_pct": round(
                            (avg - target) / target * 100,
                            2,
                        ),
                        "sample_count": len(durations),
                    }
                )
        areas.sort(
            key=lambda a: a["overshoot_pct"],
            reverse=True,
        )
        return areas

    # -- Report / stats --------------------------------------------

    def generate_timeline_report(self) -> TimelineReport:
        """Generate a comprehensive timeline report."""
        total_entries = len(self._items)
        incident_ids: set[str] = {e.incident_id for e in self._items}
        total_incidents = len(incident_ids)

        # Phase distribution
        by_phase: dict[str, int] = {}
        for e in self._items:
            key = e.phase.value
            by_phase[key] = by_phase.get(key, 0) + 1

        # Quality distribution
        by_quality: dict[str, int] = {}
        total_resolution = 0.0
        for iid in incident_ids:
            quality = self.analyze_response_quality(iid)
            key = quality.value
            by_quality[key] = by_quality.get(key, 0) + 1
            durations = self.calculate_phase_durations(iid)
            total_resolution += sum(durations.values())
        avg_resolution = round(total_resolution / total_incidents, 2) if total_incidents else 0.0

        # Bottleneck summaries
        bn_summaries: list[str] = []
        for iid in incident_ids:
            bns = self._bottlenecks.get(iid, [])
            for bn in bns:
                bn_summaries.append(
                    f"{iid}: {bn.bottleneck_type.value} ({bn.overshoot_pct}% over)",
                )

        # Recommendations
        recs: list[str] = []
        areas = self.identify_improvement_areas()
        for area in areas[:3]:
            recs.append(
                f"Phase '{area['phase']}' averages"
                f" {area['avg_duration_minutes']}m"
                f" (target {area['target_minutes']}m)"
                " — optimize response process"
            )
        critical = by_quality.get(
            ResponseQuality.CRITICAL.value,
            0,
        )
        below = by_quality.get(
            ResponseQuality.BELOW_TARGET.value,
            0,
        )
        if critical > 0:
            recs.append(f"{critical} incident(s) had critical response quality — review escalation")
        if below > 0:
            recs.append(f"{below} incident(s) below target — improve triage speed")

        return TimelineReport(
            total_incidents=total_incidents,
            total_entries=total_entries,
            avg_resolution_minutes=avg_resolution,
            by_phase=by_phase,
            by_quality=by_quality,
            bottlenecks=bn_summaries[:20],
            recommendations=recs,
        )

    def clear_data(self) -> None:
        """Clear all stored data."""
        self._items.clear()
        self._bottlenecks.clear()
        logger.info("incident_timeline.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        incidents: set[str] = set()
        phases: dict[str, int] = {}
        assignees: set[str] = set()
        total_duration = 0.0
        for e in self._items:
            incidents.add(e.incident_id)
            phases[e.phase.value] = phases.get(e.phase.value, 0) + 1
            if e.assignee:
                assignees.add(e.assignee)
            total_duration += e.duration_minutes
        total = len(self._items)
        return {
            "total_entries": total,
            "unique_incidents": len(incidents),
            "unique_assignees": len(assignees),
            "total_duration_minutes": round(
                total_duration,
                2,
            ),
            "avg_duration_minutes": (round(total_duration / total, 2) if total else 0.0),
            "phase_distribution": phases,
        }
