"""Comprehensive unit tests for the audit event bus (Phase 13 F8).

Tests cover:
- AuditEvent creation with defaults and custom fields
- AuditCategory enum values and membership
- AuditOutcome enum values and membership
- AuditSummary model defaults
- StoreSubscriber: handle, events property, get_event, query (filter by
  category/actor/action, limit, offset, reverse ordering), summary, max_events trim
- LogSubscriber: handle does not crash
- AuditEventBus: publish to all subscribers, query_events, get_event,
  summary, event_count, subscribe custom subscriber
- Custom subscriber via AuditSubscriber protocol
- Edge cases: empty bus, unknown event ID, publish with failing subscriber

Requires: pytest, pytest-asyncio
"""

from __future__ import annotations

import pytest

from shieldops.audit.event_bus import (
    AuditCategory,
    AuditEvent,
    AuditEventBus,
    AuditOutcome,
    AuditSubscriber,
    AuditSummary,
    LogSubscriber,
    StoreSubscriber,
)

# ===========================================================================
# AuditCategory Enum Tests
# ===========================================================================


class TestAuditCategory:
    """Tests for the AuditCategory StrEnum."""

    def test_agent_action_value(self):
        assert AuditCategory.AGENT_ACTION == "agent_action"

    def test_remediation_value(self):
        assert AuditCategory.REMEDIATION == "remediation"

    def test_policy_decision_value(self):
        assert AuditCategory.POLICY_DECISION == "policy_decision"

    def test_auth_value(self):
        assert AuditCategory.AUTH == "auth"

    def test_config_change_value(self):
        assert AuditCategory.CONFIG_CHANGE == "config_change"

    def test_data_access_value(self):
        assert AuditCategory.DATA_ACCESS == "data_access"

    def test_security_value(self):
        assert AuditCategory.SECURITY == "security"

    def test_category_count(self):
        assert len(AuditCategory) == 7

    def test_category_is_str(self):
        assert isinstance(AuditCategory.AGENT_ACTION, str)


# ===========================================================================
# AuditOutcome Enum Tests
# ===========================================================================


class TestAuditOutcome:
    """Tests for the AuditOutcome StrEnum."""

    def test_success_value(self):
        assert AuditOutcome.SUCCESS == "success"

    def test_failure_value(self):
        assert AuditOutcome.FAILURE == "failure"

    def test_denied_value(self):
        assert AuditOutcome.DENIED == "denied"

    def test_error_value(self):
        assert AuditOutcome.ERROR == "error"

    def test_outcome_count(self):
        assert len(AuditOutcome) == 4

    def test_outcome_is_str(self):
        assert isinstance(AuditOutcome.SUCCESS, str)


# ===========================================================================
# AuditEvent Model Tests
# ===========================================================================


class TestAuditEvent:
    """Tests for the AuditEvent Pydantic model."""

    def test_required_action_field(self):
        event = AuditEvent(action="restart_service")
        assert event.action == "restart_service"

    def test_default_id_prefix(self):
        event = AuditEvent(action="test")
        assert event.id.startswith("evt-")

    def test_default_id_uniqueness(self):
        ids = {AuditEvent(action="test").id for _ in range(50)}
        assert len(ids) == 50

    def test_default_actor(self):
        event = AuditEvent(action="test")
        assert event.actor == "system"

    def test_default_resource_empty(self):
        event = AuditEvent(action="test")
        assert event.resource == ""

    def test_default_category(self):
        event = AuditEvent(action="test")
        assert event.category == AuditCategory.AGENT_ACTION

    def test_default_outcome(self):
        event = AuditEvent(action="test")
        assert event.outcome == AuditOutcome.SUCCESS

    def test_default_metadata_empty(self):
        event = AuditEvent(action="test")
        assert event.metadata == {}

    def test_default_environment_empty(self):
        event = AuditEvent(action="test")
        assert event.environment == ""

    def test_default_correlation_id_empty(self):
        event = AuditEvent(action="test")
        assert event.correlation_id == ""

    def test_custom_actor(self):
        event = AuditEvent(action="test", actor="user-123")
        assert event.actor == "user-123"

    def test_custom_category(self):
        event = AuditEvent(action="test", category=AuditCategory.SECURITY)
        assert event.category == AuditCategory.SECURITY

    def test_custom_outcome(self):
        event = AuditEvent(action="test", outcome=AuditOutcome.DENIED)
        assert event.outcome == AuditOutcome.DENIED

    def test_custom_metadata(self):
        event = AuditEvent(action="test", metadata={"key": "value"})
        assert event.metadata == {"key": "value"}

    def test_custom_environment(self):
        event = AuditEvent(action="test", environment="production")
        assert event.environment == "production"

    def test_custom_correlation_id(self):
        event = AuditEvent(action="test", correlation_id="corr-xyz")
        assert event.correlation_id == "corr-xyz"

    def test_timestamp_is_datetime(self):
        from datetime import datetime

        event = AuditEvent(action="test")
        assert isinstance(event.timestamp, datetime)


# ===========================================================================
# AuditSummary Model Tests
# ===========================================================================


class TestAuditSummary:
    """Tests for the AuditSummary Pydantic model."""

    def test_default_total_events_zero(self):
        summary = AuditSummary()
        assert summary.total_events == 0

    def test_default_by_category_empty(self):
        summary = AuditSummary()
        assert summary.by_category == {}

    def test_default_by_actor_empty(self):
        summary = AuditSummary()
        assert summary.by_actor == {}

    def test_default_by_outcome_empty(self):
        summary = AuditSummary()
        assert summary.by_outcome == {}

    def test_custom_summary_fields(self):
        summary = AuditSummary(
            total_events=10,
            by_category={"agent_action": 5, "remediation": 5},
            by_actor={"system": 10},
            by_outcome={"success": 8, "failure": 2},
        )
        assert summary.total_events == 10
        assert summary.by_category["agent_action"] == 5


# ===========================================================================
# StoreSubscriber Tests
# ===========================================================================


class TestStoreSubscriber:
    """Tests for the in-memory StoreSubscriber."""

    @pytest.mark.asyncio
    async def test_handle_stores_event(self):
        store = StoreSubscriber()
        event = AuditEvent(action="restart_service")
        await store.handle(event)
        assert len(store.events) == 1

    @pytest.mark.asyncio
    async def test_handle_multiple_events(self):
        store = StoreSubscriber()
        for i in range(5):
            await store.handle(AuditEvent(action=f"action_{i}"))
        assert len(store.events) == 5

    @pytest.mark.asyncio
    async def test_events_property_returns_copy(self):
        store = StoreSubscriber()
        await store.handle(AuditEvent(action="test"))
        events = store.events
        events.clear()
        assert len(store.events) == 1  # Internal list unaffected

    @pytest.mark.asyncio
    async def test_get_event_found(self):
        store = StoreSubscriber()
        event = AuditEvent(id="evt-known", action="test")
        await store.handle(event)
        found = store.get_event("evt-known")
        assert found is not None
        assert found.id == "evt-known"

    @pytest.mark.asyncio
    async def test_get_event_not_found(self):
        store = StoreSubscriber()
        assert store.get_event("evt-nonexistent") is None

    @pytest.mark.asyncio
    async def test_query_by_category(self):
        store = StoreSubscriber()
        await store.handle(AuditEvent(action="a1", category=AuditCategory.SECURITY))
        await store.handle(AuditEvent(action="a2", category=AuditCategory.AUTH))
        await store.handle(AuditEvent(action="a3", category=AuditCategory.SECURITY))
        results = store.query(category="security")
        assert len(results) == 2
        assert all(e.category == AuditCategory.SECURITY for e in results)

    @pytest.mark.asyncio
    async def test_query_by_actor(self):
        store = StoreSubscriber()
        await store.handle(AuditEvent(action="a1", actor="alice"))
        await store.handle(AuditEvent(action="a2", actor="bob"))
        await store.handle(AuditEvent(action="a3", actor="alice"))
        results = store.query(actor="alice")
        assert len(results) == 2
        assert all(e.actor == "alice" for e in results)

    @pytest.mark.asyncio
    async def test_query_by_action(self):
        store = StoreSubscriber()
        await store.handle(AuditEvent(action="restart_service"))
        await store.handle(AuditEvent(action="scale_up"))
        await store.handle(AuditEvent(action="restart_service"))
        results = store.query(action="restart_service")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_combined_filters(self):
        store = StoreSubscriber()
        await store.handle(
            AuditEvent(
                action="restart_service",
                actor="alice",
                category=AuditCategory.REMEDIATION,
            )
        )
        await store.handle(
            AuditEvent(
                action="restart_service",
                actor="bob",
                category=AuditCategory.REMEDIATION,
            )
        )
        await store.handle(
            AuditEvent(
                action="scale_up",
                actor="alice",
                category=AuditCategory.REMEDIATION,
            )
        )
        results = store.query(
            category="remediation",
            actor="alice",
            action="restart_service",
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_query_returns_most_recent_first(self):
        store = StoreSubscriber()
        await store.handle(AuditEvent(id="evt-first", action="first"))
        await store.handle(AuditEvent(id="evt-second", action="second"))
        await store.handle(AuditEvent(id="evt-third", action="third"))
        results = store.query()
        assert results[0].id == "evt-third"
        assert results[2].id == "evt-first"

    @pytest.mark.asyncio
    async def test_query_limit(self):
        store = StoreSubscriber()
        for i in range(10):
            await store.handle(AuditEvent(action=f"action_{i}"))
        results = store.query(limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_query_offset(self):
        store = StoreSubscriber()
        for i in range(10):
            await store.handle(AuditEvent(action=f"action_{i}"))
        results_all = store.query(limit=50)
        results_offset = store.query(offset=2, limit=3)
        assert len(results_offset) == 3
        assert results_offset[0].id == results_all[2].id

    @pytest.mark.asyncio
    async def test_query_no_results(self):
        store = StoreSubscriber()
        await store.handle(AuditEvent(action="test", category=AuditCategory.AUTH))
        results = store.query(category="security")
        assert results == []

    @pytest.mark.asyncio
    async def test_summary_counts(self):
        store = StoreSubscriber()
        await store.handle(
            AuditEvent(
                action="a1",
                actor="alice",
                category=AuditCategory.SECURITY,
                outcome=AuditOutcome.SUCCESS,
            )
        )
        await store.handle(
            AuditEvent(
                action="a2",
                actor="bob",
                category=AuditCategory.AUTH,
                outcome=AuditOutcome.DENIED,
            )
        )
        await store.handle(
            AuditEvent(
                action="a3",
                actor="alice",
                category=AuditCategory.SECURITY,
                outcome=AuditOutcome.FAILURE,
            )
        )
        summary = store.summary()
        assert summary.total_events == 3
        assert summary.by_category["security"] == 2
        assert summary.by_category["auth"] == 1
        assert summary.by_actor["alice"] == 2
        assert summary.by_actor["bob"] == 1
        assert summary.by_outcome["success"] == 1
        assert summary.by_outcome["denied"] == 1
        assert summary.by_outcome["failure"] == 1

    @pytest.mark.asyncio
    async def test_summary_empty_store(self):
        store = StoreSubscriber()
        summary = store.summary()
        assert summary.total_events == 0
        assert summary.by_category == {}
        assert summary.by_actor == {}
        assert summary.by_outcome == {}

    @pytest.mark.asyncio
    async def test_max_events_trimming(self):
        store = StoreSubscriber(max_events=5)
        for i in range(10):
            await store.handle(AuditEvent(action=f"action_{i}"))
        assert len(store.events) == 5
        # Most recent 5 should be kept
        actions = [e.action for e in store.events]
        assert actions == [f"action_{i}" for i in range(5, 10)]


# ===========================================================================
# LogSubscriber Tests
# ===========================================================================


class TestLogSubscriber:
    """Tests for the LogSubscriber."""

    @pytest.mark.asyncio
    async def test_handle_does_not_crash(self):
        subscriber = LogSubscriber()
        event = AuditEvent(action="restart_service", actor="alice")
        # Should not raise
        await subscriber.handle(event)

    @pytest.mark.asyncio
    async def test_handle_multiple_events(self):
        subscriber = LogSubscriber()
        for i in range(5):
            await subscriber.handle(AuditEvent(action=f"action_{i}"))
        # No assertion beyond "no exception"

    @pytest.mark.asyncio
    async def test_handle_all_categories(self):
        subscriber = LogSubscriber()
        for cat in AuditCategory:
            await subscriber.handle(AuditEvent(action="test", category=cat))

    @pytest.mark.asyncio
    async def test_handle_all_outcomes(self):
        subscriber = LogSubscriber()
        for outcome in AuditOutcome:
            await subscriber.handle(AuditEvent(action="test", outcome=outcome))


# ===========================================================================
# AuditEventBus Tests
# ===========================================================================


class TestAuditEventBus:
    """Tests for the centralized AuditEventBus."""

    @pytest.mark.asyncio
    async def test_publish_stores_event(self):
        bus = AuditEventBus()
        event = AuditEvent(action="restart_service")
        await bus.publish(event)
        assert bus.event_count == 1

    @pytest.mark.asyncio
    async def test_publish_multiple_events(self):
        bus = AuditEventBus()
        for i in range(5):
            await bus.publish(AuditEvent(action=f"action_{i}"))
        assert bus.event_count == 5

    @pytest.mark.asyncio
    async def test_query_events_returns_results(self):
        bus = AuditEventBus()
        await bus.publish(AuditEvent(action="test", category=AuditCategory.SECURITY))
        await bus.publish(AuditEvent(action="test", category=AuditCategory.AUTH))
        results = bus.query_events(category="security")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_query_events_by_actor(self):
        bus = AuditEventBus()
        await bus.publish(AuditEvent(action="a1", actor="alice"))
        await bus.publish(AuditEvent(action="a2", actor="bob"))
        results = bus.query_events(actor="alice")
        assert len(results) == 1
        assert results[0].actor == "alice"

    @pytest.mark.asyncio
    async def test_query_events_by_action(self):
        bus = AuditEventBus()
        await bus.publish(AuditEvent(action="restart_service"))
        await bus.publish(AuditEvent(action="scale_up"))
        results = bus.query_events(action="restart_service")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_query_events_limit_offset(self):
        bus = AuditEventBus()
        for i in range(10):
            await bus.publish(AuditEvent(action=f"action_{i}"))
        results = bus.query_events(limit=3, offset=2)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_event_found(self):
        bus = AuditEventBus()
        event = AuditEvent(id="evt-bus-test", action="test")
        await bus.publish(event)
        found = bus.get_event("evt-bus-test")
        assert found is not None
        assert found.id == "evt-bus-test"

    @pytest.mark.asyncio
    async def test_get_event_not_found(self):
        bus = AuditEventBus()
        assert bus.get_event("evt-nonexistent") is None

    @pytest.mark.asyncio
    async def test_summary(self):
        bus = AuditEventBus()
        await bus.publish(
            AuditEvent(
                action="a1",
                actor="alice",
                category=AuditCategory.REMEDIATION,
                outcome=AuditOutcome.SUCCESS,
            )
        )
        await bus.publish(
            AuditEvent(
                action="a2",
                actor="bob",
                category=AuditCategory.SECURITY,
                outcome=AuditOutcome.FAILURE,
            )
        )
        summary = bus.summary()
        assert summary.total_events == 2
        assert summary.by_category["remediation"] == 1
        assert summary.by_category["security"] == 1
        assert summary.by_actor["alice"] == 1
        assert summary.by_outcome["success"] == 1

    @pytest.mark.asyncio
    async def test_summary_empty_bus(self):
        bus = AuditEventBus()
        summary = bus.summary()
        assert summary.total_events == 0

    @pytest.mark.asyncio
    async def test_event_count_property(self):
        bus = AuditEventBus()
        assert bus.event_count == 0
        await bus.publish(AuditEvent(action="test"))
        assert bus.event_count == 1

    @pytest.mark.asyncio
    async def test_subscribe_custom_subscriber(self):
        bus = AuditEventBus()
        received: list[AuditEvent] = []

        class CustomSub:
            async def handle(self, event: AuditEvent) -> None:
                received.append(event)

        bus.subscribe(CustomSub())
        await bus.publish(AuditEvent(action="test"))
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_multiple_custom_subscribers(self):
        bus = AuditEventBus()
        received_a: list[AuditEvent] = []
        received_b: list[AuditEvent] = []

        class SubA:
            async def handle(self, event: AuditEvent) -> None:
                received_a.append(event)

        class SubB:
            async def handle(self, event: AuditEvent) -> None:
                received_b.append(event)

        bus.subscribe(SubA())
        bus.subscribe(SubB())
        await bus.publish(AuditEvent(action="test"))
        assert len(received_a) == 1
        assert len(received_b) == 1

    @pytest.mark.asyncio
    async def test_failing_subscriber_does_not_block_others(self):
        bus = AuditEventBus()
        received: list[AuditEvent] = []

        class FailingSub:
            async def handle(self, event: AuditEvent) -> None:
                raise RuntimeError("subscriber crash")

        class GoodSub:
            async def handle(self, event: AuditEvent) -> None:
                received.append(event)

        bus.subscribe(FailingSub())
        bus.subscribe(GoodSub())
        # Should not raise despite FailingSub crashing
        await bus.publish(AuditEvent(action="test"))
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_bus_has_default_store_and_log_subscribers(self):
        bus = AuditEventBus()
        # Bus initializes with a StoreSubscriber and LogSubscriber
        assert len(bus._subscribers) >= 2
        types = [type(s).__name__ for s in bus._subscribers]
        assert "StoreSubscriber" in types
        assert "LogSubscriber" in types


# ===========================================================================
# AuditSubscriber Protocol Tests
# ===========================================================================


class TestAuditSubscriberProtocol:
    """Tests for the AuditSubscriber runtime_checkable protocol."""

    def test_store_subscriber_is_audit_subscriber(self):
        store = StoreSubscriber()
        assert isinstance(store, AuditSubscriber)

    def test_log_subscriber_is_audit_subscriber(self):
        log = LogSubscriber()
        assert isinstance(log, AuditSubscriber)

    def test_custom_class_with_handle_is_audit_subscriber(self):
        class Custom:
            async def handle(self, event: AuditEvent) -> None:
                pass

        assert isinstance(Custom(), AuditSubscriber)

    def test_object_without_handle_is_not_audit_subscriber(self):
        class NotSubscriber:
            pass

        assert not isinstance(NotSubscriber(), AuditSubscriber)
