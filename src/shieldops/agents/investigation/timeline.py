"""Incident timeline reconstruction.

Stitches events from alerts, investigations, remediations, deployments,
and config changes into an ordered chronological narrative for an incident.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class TimelineEventType(enum.StrEnum):
    ALERT = "alert"
    INVESTIGATION = "investigation"
    REMEDIATION = "remediation"
    DEPLOYMENT = "deployment"
    CONFIG_CHANGE = "config_change"
    AGENT_ACTION = "agent_action"
    ESCALATION = "escalation"
    RESOLUTION = "resolution"
    ANNOTATION = "annotation"


class TimelineStatus(enum.StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"


# ── Models ───────────────────────────────────────────────────────────


class TimelineEvent(BaseModel):
    """Single event in an incident timeline."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    event_type: TimelineEventType
    timestamp: float = Field(default_factory=time.time)
    title: str
    description: str = ""
    source: str = ""
    severity: str = "info"
    actor: str = ""
    resource: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncidentTimeline(BaseModel):
    """Complete timeline for an incident."""

    incident_id: str
    events: list[TimelineEvent] = Field(default_factory=list)
    start_time: float | None = None
    end_time: float | None = None
    affected_services: list[str] = Field(default_factory=list)
    root_cause: str = ""
    status: TimelineStatus = TimelineStatus.OPEN
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Builder ──────────────────────────────────────────────────────────


class TimelineBuilder:
    """Build and manage incident timelines.

    Parameters
    ----------
    max_events_per_incident:
        Maximum number of events stored per incident.
    retention_days:
        Days to retain resolved timelines before cleanup.
    """

    def __init__(
        self,
        max_events_per_incident: int = 1000,
        retention_days: int = 90,
    ) -> None:
        self._timelines: dict[str, IncidentTimeline] = {}
        self._max_events = max_events_per_incident
        self._retention_seconds = retention_days * 86400

    # ── Timeline CRUD ────────────────────────────────────────────

    def create_timeline(
        self,
        incident_id: str,
        affected_services: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> IncidentTimeline:
        timeline = IncidentTimeline(
            incident_id=incident_id,
            affected_services=affected_services or [],
            metadata=metadata or {},
        )
        self._timelines[incident_id] = timeline
        logger.info("timeline_created", incident_id=incident_id)
        return timeline

    def get_timeline(self, incident_id: str) -> IncidentTimeline | None:
        return self._timelines.get(incident_id)

    def list_timelines(
        self,
        status: TimelineStatus | None = None,
        limit: int = 50,
    ) -> list[IncidentTimeline]:
        timelines = sorted(
            self._timelines.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )
        if status:
            timelines = [t for t in timelines if t.status == status]
        return timelines[:limit]

    def delete_timeline(self, incident_id: str) -> bool:
        return self._timelines.pop(incident_id, None) is not None

    # ── Event management ─────────────────────────────────────────

    def add_event(
        self,
        incident_id: str,
        event: TimelineEvent,
    ) -> TimelineEvent | None:
        timeline = self._timelines.get(incident_id)
        if timeline is None:
            return None
        if len(timeline.events) >= self._max_events:
            logger.warning("timeline_events_limit", incident_id=incident_id)
            return None
        timeline.events.append(event)
        # Keep events sorted by timestamp
        timeline.events.sort(key=lambda e: e.timestamp)
        # Update start/end times
        if timeline.start_time is None or event.timestamp < timeline.start_time:
            timeline.start_time = event.timestamp
        if timeline.end_time is None or event.timestamp > timeline.end_time:
            timeline.end_time = event.timestamp
        timeline.updated_at = time.time()
        return event

    def add_annotation(
        self,
        incident_id: str,
        title: str,
        description: str = "",
        actor: str = "",
    ) -> TimelineEvent | None:
        """Add a manual annotation event."""
        event = TimelineEvent(
            event_type=TimelineEventType.ANNOTATION,
            title=title,
            description=description,
            actor=actor,
            source="user",
        )
        return self.add_event(incident_id, event)

    # ── Ingestion from other systems ─────────────────────────────

    def ingest_investigation(
        self,
        incident_id: str,
        investigation_id: str,
        title: str,
        root_cause: str = "",
        confidence: float = 0.0,
        agent_type: str = "investigation",
    ) -> TimelineEvent | None:
        event = TimelineEvent(
            event_type=TimelineEventType.INVESTIGATION,
            title=title,
            description=root_cause,
            source=agent_type,
            actor=agent_type,
            metadata={
                "investigation_id": investigation_id,
                "confidence": confidence,
            },
        )
        return self.add_event(incident_id, event)

    def ingest_remediation(
        self,
        incident_id: str,
        remediation_id: str,
        action: str,
        status: str = "",
        agent_type: str = "remediation",
    ) -> TimelineEvent | None:
        event = TimelineEvent(
            event_type=TimelineEventType.REMEDIATION,
            title=f"Remediation: {action}",
            description=f"Status: {status}",
            source=agent_type,
            actor=agent_type,
            metadata={
                "remediation_id": remediation_id,
                "action": action,
                "status": status,
            },
        )
        return self.add_event(incident_id, event)

    def ingest_alert(
        self,
        incident_id: str,
        alert_id: str,
        title: str,
        severity: str = "warning",
        source: str = "",
    ) -> TimelineEvent | None:
        event = TimelineEvent(
            event_type=TimelineEventType.ALERT,
            title=title,
            severity=severity,
            source=source,
            metadata={"alert_id": alert_id},
        )
        return self.add_event(incident_id, event)

    # ── Resolution ───────────────────────────────────────────────

    def resolve_timeline(
        self,
        incident_id: str,
        root_cause: str,
        resolved_by: str = "",
    ) -> IncidentTimeline | None:
        timeline = self._timelines.get(incident_id)
        if timeline is None:
            return None
        timeline.root_cause = root_cause
        timeline.status = TimelineStatus.RESOLVED
        timeline.end_time = time.time()
        timeline.updated_at = time.time()
        # Add resolution event
        self.add_event(
            incident_id,
            TimelineEvent(
                event_type=TimelineEventType.RESOLUTION,
                title="Incident resolved",
                description=root_cause,
                actor=resolved_by,
                source="resolution",
            ),
        )
        return timeline

    def update_status(self, incident_id: str, status: TimelineStatus) -> IncidentTimeline | None:
        timeline = self._timelines.get(incident_id)
        if timeline is None:
            return None
        timeline.status = status
        timeline.updated_at = time.time()
        return timeline

    # ── Cleanup ──────────────────────────────────────────────────

    def cleanup_old_timelines(self) -> int:
        cutoff = time.time() - self._retention_seconds
        to_remove = [
            tid
            for tid, t in self._timelines.items()
            if t.status == TimelineStatus.RESOLVED and t.updated_at < cutoff
        ]
        for tid in to_remove:
            del self._timelines[tid]
        return len(to_remove)

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        total_events = 0
        for t in self._timelines.values():
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
            total_events += len(t.events)
        return {
            "total_timelines": len(self._timelines),
            "total_events": total_events,
            "by_status": by_status,
        }
