"""Comprehensive tests for the TimelineBuilder.

Covers:
- create / get / list / delete timeline
- add_event sorted by timestamp
- add_annotation adds ANNOTATION type
- ingest_investigation / ingest_remediation / ingest_alert
- resolve_timeline sets RESOLVED + adds RESOLUTION event
- update_status
- Max events limit enforcement
- Start/end time tracking
- affected_services
- list_timelines with status filter
- cleanup_old_timelines
- Stats (total, by_status, total_events)
- Timeline not found => None
"""

from __future__ import annotations

import time
from typing import Any

from shieldops.agents.investigation.timeline import (
    TimelineBuilder,
    TimelineEvent,
    TimelineEventType,
    TimelineStatus,
)

# =========================================================================
# Helpers
# =========================================================================


def _make_event(
    event_type: TimelineEventType = TimelineEventType.ALERT,
    title: str = "Test event",
    timestamp: float | None = None,
    severity: str = "info",
    source: str = "test",
) -> TimelineEvent:
    kwargs: dict[str, Any] = {
        "event_type": event_type,
        "title": title,
        "severity": severity,
        "source": source,
    }
    if timestamp is not None:
        kwargs["timestamp"] = timestamp
    return TimelineEvent(**kwargs)


# =========================================================================
# Timeline CRUD
# =========================================================================


class TestTimelineCRUD:
    """create / get / delete basics."""

    def test_create_timeline(self) -> None:
        builder = TimelineBuilder()
        tl = builder.create_timeline("inc-1")
        assert tl.incident_id == "inc-1"
        assert tl.status == TimelineStatus.OPEN

    def test_create_timeline_with_services(self) -> None:
        builder = TimelineBuilder()
        tl = builder.create_timeline("inc-1", affected_services=["api", "db"])
        assert tl.affected_services == ["api", "db"]

    def test_create_timeline_with_metadata(self) -> None:
        builder = TimelineBuilder()
        tl = builder.create_timeline("inc-1", metadata={"env": "prod"})
        assert tl.metadata == {"env": "prod"}

    def test_get_timeline(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        assert builder.get_timeline("inc-1") is not None

    def test_get_timeline_missing(self) -> None:
        builder = TimelineBuilder()
        assert builder.get_timeline("nonexistent") is None

    def test_delete_timeline(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        assert builder.delete_timeline("inc-1") is True
        assert builder.get_timeline("inc-1") is None

    def test_delete_timeline_missing(self) -> None:
        builder = TimelineBuilder()
        assert builder.delete_timeline("nonexistent") is False

    def test_create_overwrites_existing(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1", affected_services=["old"])
        builder.create_timeline("inc-1", affected_services=["new"])
        tl = builder.get_timeline("inc-1")
        assert tl.affected_services == ["new"]


# =========================================================================
# add_event — sorted by timestamp
# =========================================================================


class TestAddEvent:
    """Events are kept sorted by timestamp."""

    def test_add_event_basic(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        event = _make_event(title="first")
        result = builder.add_event("inc-1", event)
        assert result is not None
        assert result.title == "first"

    def test_events_sorted_by_timestamp(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        e1 = _make_event(title="second", timestamp=200.0)
        e2 = _make_event(title="first", timestamp=100.0)
        e3 = _make_event(title="third", timestamp=300.0)
        builder.add_event("inc-1", e1)
        builder.add_event("inc-1", e2)
        builder.add_event("inc-1", e3)
        tl = builder.get_timeline("inc-1")
        titles = [e.title for e in tl.events]
        assert titles == ["first", "second", "third"]

    def test_add_event_to_missing_timeline(self) -> None:
        builder = TimelineBuilder()
        event = _make_event()
        assert builder.add_event("nonexistent", event) is None

    def test_add_event_updates_timestamp(self) -> None:
        builder = TimelineBuilder()
        tl = builder.create_timeline("inc-1")
        before = tl.updated_at
        builder.add_event("inc-1", _make_event())
        assert tl.updated_at >= before


# =========================================================================
# add_annotation
# =========================================================================


class TestAddAnnotation:
    """add_annotation creates ANNOTATION event type."""

    def test_annotation_type(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        event = builder.add_annotation("inc-1", title="Note", description="Details", actor="user1")
        assert event is not None
        assert event.event_type == TimelineEventType.ANNOTATION
        assert event.title == "Note"
        assert event.description == "Details"
        assert event.actor == "user1"

    def test_annotation_source_is_user(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        event = builder.add_annotation("inc-1", title="Note")
        assert event.source == "user"

    def test_annotation_missing_timeline(self) -> None:
        builder = TimelineBuilder()
        assert builder.add_annotation("nonexistent", title="Note") is None


# =========================================================================
# Ingestion methods
# =========================================================================


class TestIngestion:
    """ingest_investigation, ingest_remediation, ingest_alert."""

    def test_ingest_investigation(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        event = builder.ingest_investigation(
            "inc-1",
            investigation_id="inv-1",
            title="RCA complete",
            root_cause="Memory leak",
            confidence=0.85,
        )
        assert event is not None
        assert event.event_type == TimelineEventType.INVESTIGATION
        assert event.title == "RCA complete"
        assert event.description == "Memory leak"
        assert event.metadata["investigation_id"] == "inv-1"
        assert event.metadata["confidence"] == 0.85

    def test_ingest_remediation(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        event = builder.ingest_remediation(
            "inc-1",
            remediation_id="rem-1",
            action="restart_service",
            status="completed",
        )
        assert event is not None
        assert event.event_type == TimelineEventType.REMEDIATION
        assert "restart_service" in event.title
        assert event.metadata["remediation_id"] == "rem-1"
        assert event.metadata["action"] == "restart_service"
        assert event.metadata["status"] == "completed"

    def test_ingest_alert(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        event = builder.ingest_alert(
            "inc-1",
            alert_id="alert-1",
            title="High CPU",
            severity="critical",
            source="prometheus",
        )
        assert event is not None
        assert event.event_type == TimelineEventType.ALERT
        assert event.title == "High CPU"
        assert event.severity == "critical"
        assert event.source == "prometheus"
        assert event.metadata["alert_id"] == "alert-1"

    def test_ingest_investigation_missing_timeline(self) -> None:
        builder = TimelineBuilder()
        assert builder.ingest_investigation("none", "inv-1", "title") is None

    def test_ingest_remediation_missing_timeline(self) -> None:
        builder = TimelineBuilder()
        assert builder.ingest_remediation("none", "rem-1", "restart") is None

    def test_ingest_alert_missing_timeline(self) -> None:
        builder = TimelineBuilder()
        assert builder.ingest_alert("none", "alert-1", "title") is None


# =========================================================================
# resolve_timeline
# =========================================================================


class TestResolveTimeline:
    """resolve_timeline sets RESOLVED status and adds RESOLUTION event."""

    def test_resolve_sets_status(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        tl = builder.resolve_timeline("inc-1", root_cause="OOM", resolved_by="eng1")
        assert tl is not None
        assert tl.status == TimelineStatus.RESOLVED
        assert tl.root_cause == "OOM"

    def test_resolve_adds_resolution_event(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.resolve_timeline("inc-1", root_cause="OOM")
        tl = builder.get_timeline("inc-1")
        resolution_events = [e for e in tl.events if e.event_type == TimelineEventType.RESOLUTION]
        assert len(resolution_events) == 1
        assert resolution_events[0].title == "Incident resolved"
        assert resolution_events[0].description == "OOM"

    def test_resolve_sets_end_time(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        before = time.time()
        tl = builder.resolve_timeline("inc-1", root_cause="fix")
        assert tl.end_time is not None
        assert tl.end_time >= before

    def test_resolve_missing_timeline(self) -> None:
        builder = TimelineBuilder()
        assert builder.resolve_timeline("nonexistent", root_cause="fix") is None

    def test_resolve_sets_resolved_by_as_actor(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.resolve_timeline("inc-1", root_cause="fix", resolved_by="eng1")
        tl = builder.get_timeline("inc-1")
        resolution_events = [e for e in tl.events if e.event_type == TimelineEventType.RESOLUTION]
        assert resolution_events[0].actor == "eng1"


# =========================================================================
# update_status
# =========================================================================


class TestUpdateStatus:
    """update_status changes timeline status."""

    def test_update_status(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        tl = builder.update_status("inc-1", TimelineStatus.INVESTIGATING)
        assert tl is not None
        assert tl.status == TimelineStatus.INVESTIGATING

    def test_update_status_updates_timestamp(self) -> None:
        builder = TimelineBuilder()
        tl = builder.create_timeline("inc-1")
        before = tl.updated_at
        builder.update_status("inc-1", TimelineStatus.MITIGATING)
        assert tl.updated_at >= before

    def test_update_status_missing_timeline(self) -> None:
        builder = TimelineBuilder()
        assert builder.update_status("nonexistent", TimelineStatus.RESOLVED) is None

    def test_update_status_progression(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.update_status("inc-1", TimelineStatus.INVESTIGATING)
        builder.update_status("inc-1", TimelineStatus.MITIGATING)
        builder.update_status("inc-1", TimelineStatus.RESOLVED)
        tl = builder.get_timeline("inc-1")
        assert tl.status == TimelineStatus.RESOLVED


# =========================================================================
# Max events limit
# =========================================================================


class TestMaxEventsLimit:
    """Events beyond max_events_per_incident are rejected."""

    def test_max_events_enforced(self) -> None:
        builder = TimelineBuilder(max_events_per_incident=3)
        builder.create_timeline("inc-1")
        for i in range(3):
            assert builder.add_event("inc-1", _make_event(title=f"e{i}")) is not None
        # Fourth should be rejected
        assert builder.add_event("inc-1", _make_event(title="overflow")) is None

    def test_max_events_exact_boundary(self) -> None:
        builder = TimelineBuilder(max_events_per_incident=1)
        builder.create_timeline("inc-1")
        assert builder.add_event("inc-1", _make_event(title="only")) is not None
        assert builder.add_event("inc-1", _make_event(title="too many")) is None


# =========================================================================
# Start/end time tracking
# =========================================================================


class TestStartEndTime:
    """Timeline start and end times are maintained."""

    def test_start_time_set_from_first_event(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.add_event("inc-1", _make_event(timestamp=100.0))
        tl = builder.get_timeline("inc-1")
        assert tl.start_time == 100.0

    def test_end_time_set_from_latest_event(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.add_event("inc-1", _make_event(timestamp=100.0))
        builder.add_event("inc-1", _make_event(timestamp=300.0))
        tl = builder.get_timeline("inc-1")
        assert tl.end_time == 300.0

    def test_start_time_updated_by_earlier_event(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.add_event("inc-1", _make_event(timestamp=200.0))
        builder.add_event("inc-1", _make_event(timestamp=100.0))
        tl = builder.get_timeline("inc-1")
        assert tl.start_time == 100.0

    def test_initial_start_end_none(self) -> None:
        builder = TimelineBuilder()
        tl = builder.create_timeline("inc-1")
        assert tl.start_time is None
        assert tl.end_time is None


# =========================================================================
# affected_services
# =========================================================================


class TestAffectedServices:
    """affected_services tracks impacted services."""

    def test_affected_services_set_on_create(self) -> None:
        builder = TimelineBuilder()
        tl = builder.create_timeline("inc-1", affected_services=["api", "db", "cache"])
        assert "api" in tl.affected_services
        assert "db" in tl.affected_services
        assert "cache" in tl.affected_services

    def test_affected_services_default_empty(self) -> None:
        builder = TimelineBuilder()
        tl = builder.create_timeline("inc-1")
        assert tl.affected_services == []


# =========================================================================
# list_timelines with status filter
# =========================================================================


class TestListTimelines:
    """list_timelines with optional status filter and limit."""

    def test_list_all_timelines(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.create_timeline("inc-2")
        builder.create_timeline("inc-3")
        assert len(builder.list_timelines()) == 3

    def test_list_timelines_with_status_filter(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.create_timeline("inc-2")
        builder.update_status("inc-1", TimelineStatus.INVESTIGATING)
        result = builder.list_timelines(status=TimelineStatus.INVESTIGATING)
        assert len(result) == 1
        assert result[0].incident_id == "inc-1"

    def test_list_timelines_with_limit(self) -> None:
        builder = TimelineBuilder()
        for i in range(10):
            builder.create_timeline(f"inc-{i}")
        result = builder.list_timelines(limit=3)
        assert len(result) == 3

    def test_list_timelines_empty(self) -> None:
        builder = TimelineBuilder()
        assert builder.list_timelines() == []

    def test_list_timelines_sorted_by_created_at_desc(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-old")
        builder.create_timeline("inc-new")
        result = builder.list_timelines()
        # Most recent first
        assert result[0].incident_id == "inc-new"


# =========================================================================
# cleanup_old_timelines
# =========================================================================


class TestCleanup:
    """cleanup_old_timelines removes old resolved timelines."""

    def test_cleanup_removes_old_resolved(self) -> None:
        builder = TimelineBuilder(retention_days=0)  # immediate expiry
        builder.create_timeline("inc-1")
        builder.resolve_timeline("inc-1", root_cause="fix")
        # Manually backdate the updated_at to be old enough
        builder.get_timeline("inc-1").updated_at = time.time() - 100
        removed = builder.cleanup_old_timelines()
        assert removed == 1
        assert builder.get_timeline("inc-1") is None

    def test_cleanup_keeps_open_timelines(self) -> None:
        builder = TimelineBuilder(retention_days=0)
        builder.create_timeline("inc-1")
        # Timeline is OPEN, not RESOLVED — should not be cleaned up
        builder.get_timeline("inc-1").updated_at = time.time() - 100
        removed = builder.cleanup_old_timelines()
        assert removed == 0
        assert builder.get_timeline("inc-1") is not None

    def test_cleanup_keeps_recent_resolved(self) -> None:
        builder = TimelineBuilder(retention_days=30)
        builder.create_timeline("inc-1")
        builder.resolve_timeline("inc-1", root_cause="fix")
        removed = builder.cleanup_old_timelines()
        assert removed == 0

    def test_cleanup_returns_count(self) -> None:
        builder = TimelineBuilder(retention_days=0)
        for i in range(3):
            builder.create_timeline(f"inc-{i}")
            builder.resolve_timeline(f"inc-{i}", root_cause="fix")
            builder.get_timeline(f"inc-{i}").updated_at = time.time() - 100
        removed = builder.cleanup_old_timelines()
        assert removed == 3


# =========================================================================
# Stats
# =========================================================================


class TestStats:
    """get_stats returns summary data."""

    def test_stats_total_timelines(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.create_timeline("inc-2")
        stats = builder.get_stats()
        assert stats["total_timelines"] == 2

    def test_stats_total_events(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.add_event("inc-1", _make_event(title="e1"))
        builder.add_event("inc-1", _make_event(title="e2"))
        stats = builder.get_stats()
        assert stats["total_events"] == 2

    def test_stats_by_status(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.create_timeline("inc-2")
        builder.update_status("inc-1", TimelineStatus.INVESTIGATING)
        stats = builder.get_stats()
        assert stats["by_status"].get("investigating", 0) == 1
        assert stats["by_status"].get("open", 0) == 1

    def test_stats_empty(self) -> None:
        builder = TimelineBuilder()
        stats = builder.get_stats()
        assert stats["total_timelines"] == 0
        assert stats["total_events"] == 0
        assert stats["by_status"] == {}

    def test_stats_after_deletion(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.delete_timeline("inc-1")
        stats = builder.get_stats()
        assert stats["total_timelines"] == 0


# =========================================================================
# Edge cases
# =========================================================================


class TestEdgeCases:
    """Miscellaneous edge cases."""

    def test_timeline_has_created_at(self) -> None:
        builder = TimelineBuilder()
        tl = builder.create_timeline("inc-1")
        assert tl.created_at > 0

    def test_event_has_id(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        event = builder.add_event("inc-1", _make_event())
        assert event.id != ""

    def test_multiple_timelines_independent(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        builder.create_timeline("inc-2")
        builder.add_event("inc-1", _make_event(title="for-1"))
        tl1 = builder.get_timeline("inc-1")
        tl2 = builder.get_timeline("inc-2")
        assert len(tl1.events) == 1
        assert len(tl2.events) == 0

    def test_ingest_investigation_agent_type(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        event = builder.ingest_investigation(
            "inc-1",
            investigation_id="inv-1",
            title="RCA",
            agent_type="custom_agent",
        )
        assert event.source == "custom_agent"
        assert event.actor == "custom_agent"

    def test_ingest_remediation_agent_type(self) -> None:
        builder = TimelineBuilder()
        builder.create_timeline("inc-1")
        event = builder.ingest_remediation(
            "inc-1",
            remediation_id="rem-1",
            action="scale_up",
            agent_type="custom_rem",
        )
        assert event.source == "custom_rem"
        assert event.actor == "custom_rem"
