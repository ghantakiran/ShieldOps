"""Incident Timeline Reconstructor — auto-reconstruct timelines from logs, metrics."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EventSource(StrEnum):
    LOG = "log"
    METRIC = "metric"
    ALERT = "alert"
    DEPLOYMENT = "deployment"
    CONFIGURATION_CHANGE = "configuration_change"
    MANUAL_NOTE = "manual_note"


class TimelinePhase(StrEnum):
    PRE_INCIDENT = "pre_incident"
    TRIGGER = "trigger"
    DETECTION = "detection"
    ESCALATION = "escalation"
    MITIGATION = "mitigation"
    RESOLUTION = "resolution"


class CorrelationConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SPECULATIVE = "speculative"
    UNRELATED = "unrelated"


# --- Models ---


class TimelineEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    source: EventSource = EventSource.LOG
    phase: TimelinePhase = TimelinePhase.PRE_INCIDENT
    timestamp: float = 0.0
    description: str = ""
    service_name: str = ""
    correlation_confidence: CorrelationConfidence = CorrelationConfidence.MEDIUM
    created_at: float = Field(default_factory=time.time)


class ReconstructedTimeline(BaseModel):
    incident_id: str = ""
    events: list[TimelineEvent] = Field(default_factory=list)
    root_cause_candidates: list[str] = Field(default_factory=list)
    detection_delay_seconds: float = 0.0
    total_duration_seconds: float = 0.0
    phase_durations: dict[str, float] = Field(default_factory=dict)
    generated_at: float = Field(default_factory=time.time)


class TimelineAnalysisReport(BaseModel):
    total_events: int = 0
    incidents_analyzed: int = 0
    avg_detection_delay: float = 0.0
    avg_resolution_time: float = 0.0
    source_distribution: dict[str, int] = Field(default_factory=dict)
    phase_distribution: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentTimelineReconstructor:
    """Auto-reconstruct incident timelines from logs, metrics, alerts, and other event sources."""

    def __init__(
        self,
        max_events: int = 200000,
        correlation_window_seconds: int = 300,
    ) -> None:
        self._max_events = max_events
        self._correlation_window_seconds = correlation_window_seconds
        self._events: list[TimelineEvent] = []
        logger.info(
            "timeline_reconstructor.initialized",
            max_events=max_events,
            correlation_window_seconds=correlation_window_seconds,
        )

    def record_event(
        self,
        incident_id: str,
        source: EventSource = EventSource.LOG,
        phase: TimelinePhase = TimelinePhase.PRE_INCIDENT,
        timestamp: float = 0.0,
        description: str = "",
        service_name: str = "",
        correlation_confidence: CorrelationConfidence = CorrelationConfidence.MEDIUM,
    ) -> TimelineEvent:
        event = TimelineEvent(
            incident_id=incident_id,
            source=source,
            phase=phase,
            timestamp=timestamp if timestamp > 0 else time.time(),
            description=description,
            service_name=service_name,
            correlation_confidence=correlation_confidence,
        )
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]
        logger.info(
            "timeline_reconstructor.event_recorded",
            event_id=event.id,
            incident_id=incident_id,
            source=source,
            phase=phase,
            service_name=service_name,
        )
        return event

    def get_event(self, event_id: str) -> TimelineEvent | None:
        for e in self._events:
            if e.id == event_id:
                return e
        return None

    def list_events(
        self,
        incident_id: str | None = None,
        source: EventSource | None = None,
        phase: TimelinePhase | None = None,
        limit: int = 100,
    ) -> list[TimelineEvent]:
        results = list(self._events)
        if incident_id is not None:
            results = [e for e in results if e.incident_id == incident_id]
        if source is not None:
            results = [e for e in results if e.source == source]
        if phase is not None:
            results = [e for e in results if e.phase == phase]
        return results[-limit:]

    def _get_incident_events_sorted(self, incident_id: str) -> list[TimelineEvent]:
        """Return events for a given incident sorted by timestamp."""
        events = [e for e in self._events if e.incident_id == incident_id]
        events.sort(key=lambda e: e.timestamp)
        return events

    def _compute_phase_durations(self, events: list[TimelineEvent]) -> dict[str, float]:
        """Compute time spent in each phase from ordered events."""
        if not events:
            return {}

        phase_durations: dict[str, float] = {}
        phase_starts: dict[str, float] = {}
        phase_ends: dict[str, float] = {}

        for event in events:
            phase_key = event.phase.value
            if phase_key not in phase_starts:
                phase_starts[phase_key] = event.timestamp
            phase_ends[phase_key] = event.timestamp

        for phase_key in phase_starts:
            start = phase_starts[phase_key]
            end = phase_ends[phase_key]
            phase_durations[phase_key] = round(end - start, 2)

        return phase_durations

    def reconstruct_timeline(self, incident_id: str) -> ReconstructedTimeline:
        events = self._get_incident_events_sorted(incident_id)
        if not events:
            return ReconstructedTimeline(incident_id=incident_id)

        # Detection delay: time between first TRIGGER and first DETECTION event
        detection_delay = self.calculate_detection_delay(incident_id)

        # Total duration: first event to last event
        total_duration = events[-1].timestamp - events[0].timestamp

        # Phase durations
        phase_durations = self._compute_phase_durations(events)

        # Root cause candidates
        root_causes = self.identify_root_cause_candidates(incident_id)

        timeline = ReconstructedTimeline(
            incident_id=incident_id,
            events=events,
            root_cause_candidates=root_causes,
            detection_delay_seconds=round(detection_delay, 2),
            total_duration_seconds=round(total_duration, 2),
            phase_durations=phase_durations,
        )
        logger.info(
            "timeline_reconstructor.timeline_reconstructed",
            incident_id=incident_id,
            event_count=len(events),
            detection_delay=round(detection_delay, 2),
            total_duration=round(total_duration, 2),
        )
        return timeline

    def identify_root_cause_candidates(self, incident_id: str) -> list[str]:
        """Events in the TRIGGER phase with HIGH correlation confidence."""
        events = self._get_incident_events_sorted(incident_id)
        candidates: list[str] = []

        for event in events:
            if (
                event.phase == TimelinePhase.TRIGGER
                and event.correlation_confidence == CorrelationConfidence.HIGH
            ):
                candidate_desc = f"[{event.source.value}] {event.service_name}: {event.description}"
                candidates.append(candidate_desc)

        logger.info(
            "timeline_reconstructor.root_causes_identified",
            incident_id=incident_id,
            candidate_count=len(candidates),
        )
        return candidates

    def calculate_detection_delay(self, incident_id: str) -> float:
        """Seconds between the first TRIGGER event and the first DETECTION event."""
        events = self._get_incident_events_sorted(incident_id)

        first_trigger: float | None = None
        first_detection: float | None = None

        for event in events:
            if event.phase == TimelinePhase.TRIGGER and first_trigger is None:
                first_trigger = event.timestamp
            if event.phase == TimelinePhase.DETECTION and first_detection is None:
                first_detection = event.timestamp

        if first_trigger is not None and first_detection is not None:
            return max(0.0, first_detection - first_trigger)
        return 0.0

    def analyze_phase_transitions(self, incident_id: str) -> list[dict[str, Any]]:
        """List phase changes with timestamp gaps between consecutive events."""
        events = self._get_incident_events_sorted(incident_id)
        if len(events) < 2:
            return []

        transitions: list[dict[str, Any]] = []
        for i in range(1, len(events)):
            prev = events[i - 1]
            curr = events[i]
            if prev.phase != curr.phase:
                gap = curr.timestamp - prev.timestamp
                transitions.append(
                    {
                        "from_phase": prev.phase.value,
                        "to_phase": curr.phase.value,
                        "from_timestamp": prev.timestamp,
                        "to_timestamp": curr.timestamp,
                        "gap_seconds": round(gap, 2),
                        "from_event_id": prev.id,
                        "to_event_id": curr.id,
                    }
                )

        logger.info(
            "timeline_reconstructor.phase_transitions_analyzed",
            incident_id=incident_id,
            transition_count=len(transitions),
        )
        return transitions

    def find_correlated_events(self, event_id: str) -> list[TimelineEvent]:
        """Events within correlation_window_seconds of a given event with same incident_id."""
        target = self.get_event(event_id)
        if target is None:
            return []

        window = self._correlation_window_seconds
        correlated: list[TimelineEvent] = []

        for event in self._events:
            if event.id == target.id:
                continue
            if event.incident_id != target.incident_id:
                continue
            time_diff = abs(event.timestamp - target.timestamp)
            if time_diff <= window:
                correlated.append(event)

        correlated.sort(key=lambda e: e.timestamp)
        logger.info(
            "timeline_reconstructor.correlated_events_found",
            event_id=event_id,
            correlated_count=len(correlated),
            window_seconds=window,
        )
        return correlated

    def generate_analysis_report(self) -> TimelineAnalysisReport:
        total = len(self._events)
        if total == 0:
            return TimelineAnalysisReport()

        # Unique incidents
        incident_ids = {e.incident_id for e in self._events}
        incidents_analyzed = len(incident_ids)

        # Source distribution
        source_dist: dict[str, int] = {}
        for e in self._events:
            key = e.source.value
            source_dist[key] = source_dist.get(key, 0) + 1

        # Phase distribution
        phase_dist: dict[str, int] = {}
        for e in self._events:
            key = e.phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1

        # Average detection delay and resolution time across incidents
        total_detection_delay = 0.0
        total_resolution_time = 0.0
        valid_delay_count = 0
        valid_resolution_count = 0

        for incident_id in incident_ids:
            delay = self.calculate_detection_delay(incident_id)
            if delay > 0:
                total_detection_delay += delay
                valid_delay_count += 1

            events = self._get_incident_events_sorted(incident_id)
            if len(events) >= 2:
                duration = events[-1].timestamp - events[0].timestamp
                if duration > 0:
                    total_resolution_time += duration
                    valid_resolution_count += 1

        avg_delay = (
            round(total_detection_delay / valid_delay_count, 2) if valid_delay_count > 0 else 0.0
        )
        avg_resolution = (
            round(total_resolution_time / valid_resolution_count, 2)
            if valid_resolution_count > 0
            else 0.0
        )

        # Build recommendations
        recommendations: list[str] = []
        if avg_delay > 300:
            recommendations.append(
                f"Average detection delay is {avg_delay:.0f}s — "
                f"improve monitoring alerting thresholds to reduce delay below 5 minutes"
            )
        if avg_resolution > 3600:
            recommendations.append(
                f"Average resolution time is {avg_resolution:.0f}s — "
                f"create runbooks for common incident patterns to accelerate resolution"
            )

        trigger_count = phase_dist.get(TimelinePhase.TRIGGER.value, 0)
        detection_count = phase_dist.get(TimelinePhase.DETECTION.value, 0)
        if trigger_count > 0 and detection_count == 0:
            recommendations.append(
                "Trigger events found with no detection events — "
                "review alerting pipeline for missed detections"
            )

        manual_count = source_dist.get(EventSource.MANUAL_NOTE.value, 0)
        if manual_count > total * 0.3:
            recommendations.append(
                "Over 30% of events are manual notes — increase automated observability coverage"
            )

        report = TimelineAnalysisReport(
            total_events=total,
            incidents_analyzed=incidents_analyzed,
            avg_detection_delay=avg_delay,
            avg_resolution_time=avg_resolution,
            source_distribution=source_dist,
            phase_distribution=phase_dist,
            recommendations=recommendations,
        )
        logger.info(
            "timeline_reconstructor.report_generated",
            total_events=total,
            incidents_analyzed=incidents_analyzed,
            avg_detection_delay=avg_delay,
            avg_resolution_time=avg_resolution,
        )
        return report

    def clear_data(self) -> None:
        self._events.clear()
        logger.info("timeline_reconstructor.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        incident_ids = {e.incident_id for e in self._events}
        sources = {e.source.value for e in self._events}
        phases = {e.phase.value for e in self._events}
        return {
            "total_events": len(self._events),
            "unique_incidents": len(incident_ids),
            "event_sources": sorted(sources),
            "event_phases": sorted(phases),
        }
