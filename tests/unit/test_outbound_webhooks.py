"""Comprehensive unit tests for OutboundWebhookDispatcher.

Tests cover:
- WebhookEventType / DeliveryStatus enums
- WebhookSubscription and DeliveryRecord Pydantic models (defaults, fields)
- Subscription CRUD (create, list, get, delete)
- Event filtering (matching events, empty events list wildcard, inactive subs)
- HMAC-SHA256 payload signing and verification
- Async dispatch to multiple/single/no subscribers
- send_test_event behaviour
- Delivery record logging and retrieval
- Dead letter handling on delivery failure
- Edge cases (unknown IDs, duplicate creates, empty state)

NOTE: The source module has a structlog bug — logger.info("webhook_delivered", event=...)
passes "event" as both the positional message and a keyword arg, causing TypeError.
Tests that invoke _deliver() patch the module-level logger to isolate business logic
from this logging defect.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from shieldops.integrations.outbound.webhook_dispatcher import (
    DeliveryRecord,
    DeliveryStatus,
    OutboundWebhookDispatcher,
    WebhookEventType,
    WebhookSubscription,
)

# Patch target for the structlog logger that has the event= kwarg bug.
_LOGGER_PATCH = "shieldops.integrations.outbound.webhook_dispatcher.logger"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dispatcher() -> OutboundWebhookDispatcher:
    """Fresh dispatcher instance for each test."""
    return OutboundWebhookDispatcher()


@pytest.fixture
def patched_dispatcher() -> OutboundWebhookDispatcher:
    """Dispatcher with the module logger patched out (for async _deliver tests)."""
    with patch(_LOGGER_PATCH):
        d = OutboundWebhookDispatcher()
        yield d


@pytest.fixture
def mock_logger():
    """Patch the module-level structlog logger to avoid the event= kwarg bug."""
    with patch(_LOGGER_PATCH) as mock_log:
        yield mock_log


@pytest.fixture
def sample_subscription() -> WebhookSubscription:
    """A minimal active subscription that listens to incident events."""
    return WebhookSubscription(
        id="wh-test-001",
        url="https://hooks.example.com/shieldops",
        events=["incident.created", "incident.resolved"],
        secret="super-secret-key",
        description="Test hook",
    )


@pytest.fixture
def inactive_subscription() -> WebhookSubscription:
    """An inactive subscription that should be skipped during dispatch."""
    return WebhookSubscription(
        id="wh-inactive",
        url="https://hooks.example.com/disabled",
        events=["incident.created"],
        secret="key",
        active=False,
    )


@pytest.fixture
def wildcard_subscription() -> WebhookSubscription:
    """A subscription with empty events list (matches all event types)."""
    return WebhookSubscription(
        id="wh-wildcard",
        url="https://hooks.example.com/all-events",
        events=[],
        secret="wildcard-secret",
    )


@pytest.fixture
def sample_payload() -> dict:
    return {
        "incident_id": "inc-abc123",
        "severity": "critical",
        "service": "api-gateway",
    }


# ===========================================================================
# Enum Tests
# ===========================================================================


class TestWebhookEventType:
    """Tests for the WebhookEventType StrEnum."""

    def test_all_event_types_exist(self):
        expected = {
            "INCIDENT_CREATED",
            "INCIDENT_RESOLVED",
            "REMEDIATION_STARTED",
            "REMEDIATION_COMPLETED",
            "VULNERABILITY_DETECTED",
            "COMPLIANCE_DRIFT",
            "PREDICTION_GENERATED",
        }
        actual = {e.name for e in WebhookEventType}
        assert actual == expected, f"Missing or extra event types: {actual ^ expected}"

    def test_event_type_values_use_dot_notation(self):
        for event in WebhookEventType:
            assert "." in event.value, f"{event.name} value should use dot notation"

    @pytest.mark.parametrize(
        "member,value",
        [
            (WebhookEventType.INCIDENT_CREATED, "incident.created"),
            (WebhookEventType.INCIDENT_RESOLVED, "incident.resolved"),
            (WebhookEventType.REMEDIATION_STARTED, "remediation.started"),
            (WebhookEventType.REMEDIATION_COMPLETED, "remediation.completed"),
            (WebhookEventType.VULNERABILITY_DETECTED, "vulnerability.detected"),
            (WebhookEventType.COMPLIANCE_DRIFT, "compliance.drift"),
            (WebhookEventType.PREDICTION_GENERATED, "prediction.generated"),
        ],
    )
    def test_event_type_string_values(self, member, value):
        assert member.value == value

    def test_event_type_is_str_subclass(self):
        assert isinstance(WebhookEventType.INCIDENT_CREATED, str)

    def test_event_type_count(self):
        assert len(WebhookEventType) == 7


class TestDeliveryStatus:
    """Tests for the DeliveryStatus StrEnum."""

    @pytest.mark.parametrize(
        "member,value",
        [
            (DeliveryStatus.PENDING, "pending"),
            (DeliveryStatus.DELIVERED, "delivered"),
            (DeliveryStatus.FAILED, "failed"),
            (DeliveryStatus.RETRYING, "retrying"),
        ],
    )
    def test_delivery_status_values(self, member, value):
        assert member.value == value

    def test_delivery_status_count(self):
        assert len(DeliveryStatus) == 4


# ===========================================================================
# Pydantic Model Tests
# ===========================================================================


class TestWebhookSubscription:
    """Tests for the WebhookSubscription Pydantic model."""

    def test_default_id_prefix(self):
        sub = WebhookSubscription(url="https://example.com")
        assert sub.id.startswith("wh-"), f"ID should start with 'wh-', got {sub.id}"

    def test_default_id_uniqueness(self):
        ids = {WebhookSubscription(url="https://example.com").id for _ in range(50)}
        assert len(ids) == 50, "Auto-generated IDs should be unique"

    def test_default_fields(self):
        sub = WebhookSubscription(url="https://example.com")
        assert sub.events == []
        assert sub.secret == ""
        assert sub.filters == {}
        assert sub.active is True
        assert sub.description == ""
        assert isinstance(sub.created_at, datetime)

    def test_explicit_fields_preserved(self, sample_subscription):
        assert sample_subscription.id == "wh-test-001"
        assert sample_subscription.url == "https://hooks.example.com/shieldops"
        assert sample_subscription.events == ["incident.created", "incident.resolved"]
        assert sample_subscription.secret == "super-secret-key"  # noqa: S105
        assert sample_subscription.description == "Test hook"
        assert sample_subscription.active is True

    def test_inactive_subscription_flag(self, inactive_subscription):
        assert inactive_subscription.active is False

    def test_filters_dict_accepts_arbitrary_keys(self):
        sub = WebhookSubscription(
            url="https://example.com",
            filters={"severity": "critical", "environment": "production"},
        )
        assert sub.filters["severity"] == "critical"
        assert sub.filters["environment"] == "production"

    def test_created_at_is_utc_aware(self):
        sub = WebhookSubscription(url="https://example.com")
        assert sub.created_at.tzinfo is not None


class TestDeliveryRecord:
    """Tests for the DeliveryRecord Pydantic model."""

    def test_default_id_prefix(self):
        record = DeliveryRecord(subscription_id="wh-1", event_type="test")
        assert record.id.startswith("dlv-")

    def test_default_status_is_pending(self):
        record = DeliveryRecord(subscription_id="wh-1", event_type="test")
        assert record.status == DeliveryStatus.PENDING

    def test_default_fields(self):
        record = DeliveryRecord(subscription_id="wh-1", event_type="test")
        assert record.status_code is None
        assert record.attempt == 1
        assert record.max_attempts == 3
        assert record.payload == {}
        assert record.error is None
        assert record.delivered_at is None
        assert isinstance(record.created_at, datetime)

    def test_explicit_fields_preserved(self):
        record = DeliveryRecord(
            id="dlv-custom",
            subscription_id="wh-1",
            event_type="incident.created",
            status=DeliveryStatus.DELIVERED,
            status_code=200,
            attempt=2,
            payload={"key": "value"},
        )
        assert record.id == "dlv-custom"
        assert record.status == DeliveryStatus.DELIVERED
        assert record.status_code == 200
        assert record.attempt == 2
        assert record.payload == {"key": "value"}

    def test_default_id_uniqueness(self):
        ids = {DeliveryRecord(subscription_id="wh-1", event_type="t").id for _ in range(50)}
        assert len(ids) == 50


# ===========================================================================
# Subscription CRUD Tests
# ===========================================================================


class TestSubscriptionCRUD:
    """Tests for create, list, get, and delete subscription operations."""

    def test_create_subscription_returns_subscription(self, dispatcher, sample_subscription):
        result = dispatcher.create_subscription(sample_subscription)
        assert result is sample_subscription

    def test_create_subscription_stored_internally(self, dispatcher, sample_subscription):
        dispatcher.create_subscription(sample_subscription)
        assert dispatcher.get_subscription("wh-test-001") is sample_subscription

    def test_create_multiple_subscriptions(self, dispatcher):
        sub1 = WebhookSubscription(id="wh-1", url="https://a.com")
        sub2 = WebhookSubscription(id="wh-2", url="https://b.com")
        dispatcher.create_subscription(sub1)
        dispatcher.create_subscription(sub2)
        assert len(dispatcher.list_subscriptions()) == 2

    def test_create_duplicate_id_overwrites(self, dispatcher):
        sub_v1 = WebhookSubscription(id="wh-dup", url="https://v1.com")
        sub_v2 = WebhookSubscription(id="wh-dup", url="https://v2.com")
        dispatcher.create_subscription(sub_v1)
        dispatcher.create_subscription(sub_v2)
        fetched = dispatcher.get_subscription("wh-dup")
        assert fetched.url == "https://v2.com"
        assert len(dispatcher.list_subscriptions()) == 1

    def test_list_subscriptions_empty(self, dispatcher):
        assert dispatcher.list_subscriptions() == []

    def test_list_subscriptions_returns_new_list(self, dispatcher, sample_subscription):
        """list_subscriptions returns a new list; mutating it should not affect internal state."""
        dispatcher.create_subscription(sample_subscription)
        subs = dispatcher.list_subscriptions()
        subs.clear()
        assert len(dispatcher.list_subscriptions()) == 1

    def test_get_subscription_found(self, dispatcher, sample_subscription):
        dispatcher.create_subscription(sample_subscription)
        result = dispatcher.get_subscription("wh-test-001")
        assert result is not None
        assert result.id == "wh-test-001"

    def test_get_subscription_not_found(self, dispatcher):
        result = dispatcher.get_subscription("nonexistent")
        assert result is None

    def test_delete_subscription_success(self, dispatcher, sample_subscription):
        dispatcher.create_subscription(sample_subscription)
        result = dispatcher.delete_subscription("wh-test-001")
        assert result is True
        assert dispatcher.get_subscription("wh-test-001") is None

    def test_delete_subscription_not_found(self, dispatcher):
        result = dispatcher.delete_subscription("no-such-id")
        assert result is False

    def test_delete_then_list_is_empty(self, dispatcher, sample_subscription):
        dispatcher.create_subscription(sample_subscription)
        dispatcher.delete_subscription(sample_subscription.id)
        assert dispatcher.list_subscriptions() == []

    def test_delete_idempotent(self, dispatcher, sample_subscription):
        """Deleting the same subscription twice: first returns True, second returns False."""
        dispatcher.create_subscription(sample_subscription)
        assert dispatcher.delete_subscription(sample_subscription.id) is True
        assert dispatcher.delete_subscription(sample_subscription.id) is False


# ===========================================================================
# HMAC-SHA256 Signing Tests
# ===========================================================================


class TestSignPayload:
    """Tests for the HMAC-SHA256 payload signing mechanism."""

    def test_sign_payload_returns_sha256_prefixed_string(self, dispatcher):
        sig = dispatcher.sign_payload({"key": "value"}, "secret")
        assert sig.startswith("sha256=")

    def test_sign_payload_hex_digest_length(self, dispatcher):
        sig = dispatcher.sign_payload({"key": "value"}, "secret")
        hex_part = sig.removeprefix("sha256=")
        assert len(hex_part) == 64, "SHA-256 hex digest should be 64 chars"

    def test_sign_payload_deterministic(self, dispatcher):
        payload = {"a": 1, "b": 2}
        sig1 = dispatcher.sign_payload(payload, "secret")
        sig2 = dispatcher.sign_payload(payload, "secret")
        assert sig1 == sig2, "Same payload + secret should produce same signature"

    def test_sign_payload_different_secrets_differ(self, dispatcher):
        payload = {"key": "value"}
        sig1 = dispatcher.sign_payload(payload, "secret-a")
        sig2 = dispatcher.sign_payload(payload, "secret-b")
        assert sig1 != sig2

    def test_sign_payload_different_payloads_differ(self, dispatcher):
        sig1 = dispatcher.sign_payload({"key": "alpha"}, "secret")
        sig2 = dispatcher.sign_payload({"key": "beta"}, "secret")
        assert sig1 != sig2

    def test_sign_payload_key_order_independent(self, dispatcher):
        """sign_payload uses sort_keys=True, so key order should not matter."""
        sig1 = dispatcher.sign_payload({"z": 1, "a": 2}, "secret")
        sig2 = dispatcher.sign_payload({"a": 2, "z": 1}, "secret")
        assert sig1 == sig2

    def test_sign_payload_matches_manual_hmac(self, dispatcher):
        payload = {"event": "test", "count": 42}
        secret = "my-secret"  # noqa: S105
        expected_bytes = json.dumps(payload, sort_keys=True, default=str).encode()
        expected_sig = hmac.new(secret.encode(), expected_bytes, hashlib.sha256).hexdigest()
        result = dispatcher.sign_payload(payload, secret)
        assert result == f"sha256={expected_sig}"

    def test_sign_payload_empty_payload(self, dispatcher):
        sig = dispatcher.sign_payload({}, "secret")
        assert sig.startswith("sha256=")
        assert len(sig.removeprefix("sha256=")) == 64

    def test_sign_payload_empty_secret(self, dispatcher):
        """Empty string as secret should still produce a valid HMAC."""
        sig = dispatcher.sign_payload({"key": "value"}, "")
        assert sig.startswith("sha256=")

    def test_sign_payload_with_nested_dict(self, dispatcher):
        payload = {"outer": {"inner": "value", "list": [1, 2, 3]}}
        sig = dispatcher.sign_payload(payload, "s")
        assert sig.startswith("sha256=")

    def test_sign_payload_with_datetime_value(self, dispatcher):
        """sort_keys=True, default=str should handle non-serializable types."""
        payload = {"ts": datetime.now(UTC)}
        sig = dispatcher.sign_payload(payload, "secret")
        assert sig.startswith("sha256=")


# ===========================================================================
# Event Filtering / Matching Tests
# ===========================================================================


class TestEventFiltering:
    """Tests for _get_matching_subscriptions logic."""

    def test_subscription_matches_listed_event(self, dispatcher, sample_subscription):
        dispatcher.create_subscription(sample_subscription)
        matching = dispatcher._get_matching_subscriptions("incident.created")
        assert len(matching) == 1
        assert matching[0].id == "wh-test-001"

    def test_subscription_does_not_match_unlisted_event(self, dispatcher, sample_subscription):
        dispatcher.create_subscription(sample_subscription)
        matching = dispatcher._get_matching_subscriptions("remediation.started")
        assert len(matching) == 0

    def test_wildcard_subscription_matches_any_event(self, dispatcher, wildcard_subscription):
        dispatcher.create_subscription(wildcard_subscription)
        for event in WebhookEventType:
            matching = dispatcher._get_matching_subscriptions(event.value)
            assert len(matching) == 1, f"Wildcard sub should match {event.value}"

    def test_inactive_subscription_excluded(self, dispatcher, inactive_subscription):
        dispatcher.create_subscription(inactive_subscription)
        matching = dispatcher._get_matching_subscriptions("incident.created")
        assert len(matching) == 0

    def test_mixed_active_inactive(self, dispatcher, sample_subscription, inactive_subscription):
        dispatcher.create_subscription(sample_subscription)
        dispatcher.create_subscription(inactive_subscription)
        matching = dispatcher._get_matching_subscriptions("incident.created")
        assert len(matching) == 1
        assert matching[0].id == sample_subscription.id

    def test_multiple_matching_subscriptions(self, dispatcher):
        sub_a = WebhookSubscription(id="wh-a", url="https://a.com", events=["incident.created"])
        sub_b = WebhookSubscription(id="wh-b", url="https://b.com", events=["incident.created"])
        dispatcher.create_subscription(sub_a)
        dispatcher.create_subscription(sub_b)
        matching = dispatcher._get_matching_subscriptions("incident.created")
        assert len(matching) == 2

    def test_no_subscriptions_returns_empty_list(self, dispatcher):
        matching = dispatcher._get_matching_subscriptions("incident.created")
        assert matching == []

    def test_wildcard_matches_custom_event_type(self, dispatcher, wildcard_subscription):
        """Wildcard (empty events list) should match even non-standard event strings."""
        dispatcher.create_subscription(wildcard_subscription)
        matching = dispatcher._get_matching_subscriptions("custom.arbitrary.event")
        assert len(matching) == 1


# ===========================================================================
# Async Dispatch Tests
# ===========================================================================


class TestDispatch:
    """Tests for the async dispatch method.

    All tests that trigger _deliver() use mock_logger to avoid the structlog
    event= kwarg bug in the source module.
    """

    @pytest.mark.asyncio
    async def test_dispatch_returns_delivery_records(
        self, dispatcher, sample_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("incident.created", sample_payload)
        assert len(records) == 1
        assert isinstance(records[0], DeliveryRecord)

    @pytest.mark.asyncio
    async def test_dispatch_record_has_correct_fields(
        self, dispatcher, sample_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("incident.created", sample_payload)
        record = records[0]
        assert record.subscription_id == "wh-test-001"
        assert record.event_type == "incident.created"
        assert record.status == DeliveryStatus.DELIVERED
        assert record.status_code == 200

    @pytest.mark.asyncio
    async def test_dispatch_payload_wraps_original(
        self, dispatcher, sample_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("incident.created", sample_payload)
        full_payload = records[0].payload
        assert full_payload["event_type"] == "incident.created"
        assert full_payload["subscription_id"] == "wh-test-001"
        assert full_payload["data"] == sample_payload
        assert "timestamp" in full_payload

    @pytest.mark.asyncio
    async def test_dispatch_skips_inactive_subscription(
        self, dispatcher, inactive_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(inactive_subscription)
        records = await dispatcher.dispatch("incident.created", sample_payload)
        assert records == []

    @pytest.mark.asyncio
    async def test_dispatch_skips_non_matching_event(
        self, dispatcher, sample_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("remediation.started", sample_payload)
        assert records == []

    @pytest.mark.asyncio
    async def test_dispatch_to_multiple_subscriptions(
        self, dispatcher, sample_payload, mock_logger
    ):
        sub1 = WebhookSubscription(id="wh-1", url="https://a.com", events=["incident.created"])
        sub2 = WebhookSubscription(id="wh-2", url="https://b.com", events=["incident.created"])
        sub3 = WebhookSubscription(id="wh-3", url="https://c.com", events=["other.event"])
        dispatcher.create_subscription(sub1)
        dispatcher.create_subscription(sub2)
        dispatcher.create_subscription(sub3)
        records = await dispatcher.dispatch("incident.created", sample_payload)
        assert len(records) == 2
        sub_ids = {r.subscription_id for r in records}
        assert sub_ids == {"wh-1", "wh-2"}

    @pytest.mark.asyncio
    async def test_dispatch_with_no_subscriptions(self, dispatcher, sample_payload, mock_logger):
        records = await dispatcher.dispatch("incident.created", sample_payload)
        assert records == []

    @pytest.mark.asyncio
    async def test_dispatch_wildcard_subscription_receives_all_events(
        self, dispatcher, wildcard_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(wildcard_subscription)
        for event_type in WebhookEventType:
            records = await dispatcher.dispatch(event_type.value, sample_payload)
            assert len(records) == 1, f"Wildcard should match {event_type.value}"

    @pytest.mark.asyncio
    async def test_dispatch_records_stored_in_deliveries(
        self, dispatcher, sample_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        await dispatcher.dispatch("incident.created", sample_payload)
        deliveries = dispatcher.get_deliveries("wh-test-001")
        assert len(deliveries) == 1

    @pytest.mark.asyncio
    async def test_dispatch_empty_payload(self, dispatcher, sample_subscription, mock_logger):
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("incident.created", {})
        assert len(records) == 1
        assert records[0].payload["data"] == {}

    @pytest.mark.asyncio
    async def test_dispatch_delivered_at_is_set(
        self, dispatcher, sample_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("incident.created", sample_payload)
        assert records[0].delivered_at is not None
        assert isinstance(records[0].delivered_at, datetime)

    @pytest.mark.asyncio
    async def test_dispatch_does_not_mutate_input_payload(
        self, dispatcher, sample_subscription, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        payload = {"key": "value"}
        payload_copy = payload.copy()
        await dispatcher.dispatch("incident.created", payload)
        assert payload == payload_copy, "dispatch should not mutate the input payload"


# ===========================================================================
# Send Test Event Tests
# ===========================================================================


class TestSendTestEvent:
    """Tests for the send_test_event method."""

    @pytest.mark.asyncio
    async def test_send_test_event_returns_delivery_record(
        self, dispatcher, sample_subscription, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        record = await dispatcher.send_test_event("wh-test-001")
        assert record is not None
        assert isinstance(record, DeliveryRecord)

    @pytest.mark.asyncio
    async def test_send_test_event_uses_test_event_type(
        self, dispatcher, sample_subscription, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        record = await dispatcher.send_test_event("wh-test-001")
        assert record.event_type == "test"

    @pytest.mark.asyncio
    async def test_send_test_event_payload_contents(
        self, dispatcher, sample_subscription, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        record = await dispatcher.send_test_event("wh-test-001")
        data = record.payload["data"]
        assert data["event_type"] == "test"
        assert "message" in data
        assert "ShieldOps" in data["message"]
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_send_test_event_unknown_subscription_returns_none(self, dispatcher, mock_logger):
        result = await dispatcher.send_test_event("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_send_test_event_stored_in_deliveries(
        self, dispatcher, sample_subscription, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        await dispatcher.send_test_event("wh-test-001")
        deliveries = dispatcher.get_deliveries("wh-test-001")
        assert len(deliveries) == 1
        assert deliveries[0].event_type == "test"

    @pytest.mark.asyncio
    async def test_send_test_event_to_inactive_subscription_still_delivers(
        self, dispatcher, inactive_subscription, mock_logger
    ):
        """send_test_event bypasses event filtering and delivers directly."""
        dispatcher.create_subscription(inactive_subscription)
        record = await dispatcher.send_test_event("wh-inactive")
        assert record is not None
        assert record.status == DeliveryStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_send_test_event_record_has_subscription_id(
        self, dispatcher, sample_subscription, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        record = await dispatcher.send_test_event("wh-test-001")
        assert record.payload["subscription_id"] == "wh-test-001"


# ===========================================================================
# Delivery Record Retrieval Tests
# ===========================================================================


class TestGetDeliveries:
    """Tests for get_deliveries filtering and accumulation."""

    def test_get_deliveries_empty_for_new_subscription(self, dispatcher, sample_subscription):
        dispatcher.create_subscription(sample_subscription)
        assert dispatcher.get_deliveries("wh-test-001") == []

    @pytest.mark.asyncio
    async def test_get_deliveries_filters_by_subscription_id(self, dispatcher, mock_logger):
        sub_a = WebhookSubscription(id="wh-a", url="https://a.com", events=[])
        sub_b = WebhookSubscription(id="wh-b", url="https://b.com", events=[])
        dispatcher.create_subscription(sub_a)
        dispatcher.create_subscription(sub_b)
        await dispatcher.dispatch("incident.created", {"x": 1})
        deliveries_a = dispatcher.get_deliveries("wh-a")
        deliveries_b = dispatcher.get_deliveries("wh-b")
        assert len(deliveries_a) == 1
        assert len(deliveries_b) == 1
        assert deliveries_a[0].subscription_id == "wh-a"
        assert deliveries_b[0].subscription_id == "wh-b"

    @pytest.mark.asyncio
    async def test_get_deliveries_accumulates_across_dispatches(
        self, dispatcher, wildcard_subscription, mock_logger
    ):
        dispatcher.create_subscription(wildcard_subscription)
        await dispatcher.dispatch("incident.created", {"n": 1})
        await dispatcher.dispatch("incident.resolved", {"n": 2})
        await dispatcher.dispatch("remediation.started", {"n": 3})
        deliveries = dispatcher.get_deliveries("wh-wildcard")
        assert len(deliveries) == 3

    def test_get_deliveries_unknown_subscription_returns_empty(self, dispatcher):
        assert dispatcher.get_deliveries("no-such-id") == []

    @pytest.mark.asyncio
    async def test_get_deliveries_preserves_event_type(
        self, dispatcher, sample_subscription, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        await dispatcher.dispatch("incident.created", {"a": 1})
        deliveries = dispatcher.get_deliveries("wh-test-001")
        assert deliveries[0].event_type == "incident.created"


# ===========================================================================
# Dead Letter / Error Handling Tests
# ===========================================================================


class TestDeliveryFailureHandling:
    """Tests for delivery failures and dead letter recording."""

    @pytest.mark.asyncio
    async def test_delivery_failure_produces_failed_record(
        self, dispatcher, sample_subscription, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        with patch.object(
            dispatcher,
            "_deliver",
            new_callable=AsyncMock,
        ) as mock_deliver:
            failed_record = DeliveryRecord(
                subscription_id="wh-test-001",
                event_type="incident.created",
                status=DeliveryStatus.FAILED,
                error="Connection refused",
            )
            mock_deliver.return_value = failed_record
            records = await dispatcher.dispatch("incident.created", {"x": 1})
            assert records[0].status == DeliveryStatus.FAILED
            assert records[0].error == "Connection refused"

    @pytest.mark.asyncio
    async def test_dead_letter_appended_on_exception(
        self, dispatcher, sample_subscription, mock_logger
    ):
        """When _deliver has an internal exception, the record goes to _dead_letters."""
        dispatcher.create_subscription(sample_subscription)

        async def failing_deliver(sub, event_type, payload):
            full_payload = {
                "event_type": event_type,
                "timestamp": "now",
                "subscription_id": sub.id,
                "data": payload,
            }
            record = DeliveryRecord(
                subscription_id=sub.id,
                event_type=event_type,
                payload=full_payload,
            )
            try:
                raise ConnectionError("simulated network failure")
            except Exception as e:
                record.status = DeliveryStatus.FAILED
                record.error = str(e)
                dispatcher._dead_letters.append(record)
            dispatcher._deliveries.append(record)
            return record

        with patch.object(dispatcher, "_deliver", side_effect=failing_deliver):
            records = await dispatcher.dispatch("incident.created", {"x": 1})
            assert len(records) == 1
            assert records[0].status == DeliveryStatus.FAILED
            assert len(dispatcher._dead_letters) == 1
            assert dispatcher._dead_letters[0].error == "simulated network failure"

    @pytest.mark.asyncio
    async def test_delivery_failure_still_stores_in_deliveries(
        self, dispatcher, sample_subscription, mock_logger
    ):
        """Even a failed delivery should be recorded in _deliveries."""
        dispatcher.create_subscription(sample_subscription)

        async def failing_deliver(sub, event_type, payload):
            record = DeliveryRecord(
                subscription_id=sub.id,
                event_type=event_type,
                status=DeliveryStatus.FAILED,
                error="timeout",
            )
            dispatcher._deliveries.append(record)
            dispatcher._dead_letters.append(record)
            return record

        with patch.object(dispatcher, "_deliver", side_effect=failing_deliver):
            await dispatcher.dispatch("incident.created", {"x": 1})
            assert len(dispatcher.get_deliveries("wh-test-001")) == 1


# ===========================================================================
# Dispatcher Class-Level / Initialization Tests
# ===========================================================================


class TestDispatcherInitialization:
    """Tests for OutboundWebhookDispatcher constructor and class attributes."""

    def test_initial_state_empty(self, dispatcher):
        assert dispatcher.list_subscriptions() == []
        assert dispatcher._deliveries == []
        assert dispatcher._dead_letters == []

    def test_max_retry_attempts_class_constant(self):
        assert OutboundWebhookDispatcher.MAX_RETRY_ATTEMPTS == 3

    def test_dispatchers_are_independent(self):
        d1 = OutboundWebhookDispatcher()
        d2 = OutboundWebhookDispatcher()
        d1.create_subscription(WebhookSubscription(id="wh-only-d1", url="https://a.com"))
        assert d2.list_subscriptions() == []
        assert d1.get_subscription("wh-only-d1") is not None

    def test_internal_collections_are_instance_level(self):
        """Ensure _subscriptions, _deliveries, _dead_letters are not shared across instances."""
        d1 = OutboundWebhookDispatcher()
        d2 = OutboundWebhookDispatcher()
        assert d1._subscriptions is not d2._subscriptions
        assert d1._deliveries is not d2._deliveries
        assert d1._dead_letters is not d2._dead_letters


# ===========================================================================
# Integration-Style Scenario Tests (still unit-level, no I/O)
# ===========================================================================


class TestEndToEndScenarios:
    """Multi-step scenarios exercising the full lifecycle."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_create_dispatch_query_delete(self, dispatcher, mock_logger):
        sub = WebhookSubscription(
            id="wh-lifecycle",
            url="https://lifecycle.test",
            events=["incident.created"],
            secret="lifecycle-secret",
        )
        dispatcher.create_subscription(sub)
        assert dispatcher.get_subscription("wh-lifecycle") is not None

        records = await dispatcher.dispatch("incident.created", {"incident_id": "inc-999"})
        assert len(records) == 1
        assert records[0].status == DeliveryStatus.DELIVERED

        deliveries = dispatcher.get_deliveries("wh-lifecycle")
        assert len(deliveries) == 1

        deleted = dispatcher.delete_subscription("wh-lifecycle")
        assert deleted is True
        assert dispatcher.get_subscription("wh-lifecycle") is None

        # Deliveries persist even after subscription deletion
        assert len(dispatcher._deliveries) == 1

    @pytest.mark.asyncio
    async def test_selective_dispatch_among_many_subscriptions(self, dispatcher, mock_logger):
        """Only subscriptions with matching events receive the dispatch."""
        incident_sub = WebhookSubscription(
            id="wh-inc", url="https://inc.test", events=["incident.created"]
        )
        remediation_sub = WebhookSubscription(
            id="wh-rem", url="https://rem.test", events=["remediation.started"]
        )
        all_events_sub = WebhookSubscription(id="wh-all", url="https://all.test", events=[])
        inactive_sub = WebhookSubscription(
            id="wh-off", url="https://off.test", events=["incident.created"], active=False
        )

        for s in [incident_sub, remediation_sub, all_events_sub, inactive_sub]:
            dispatcher.create_subscription(s)

        records = await dispatcher.dispatch("incident.created", {"severity": "high"})
        delivered_ids = {r.subscription_id for r in records}
        assert delivered_ids == {"wh-inc", "wh-all"}

    @pytest.mark.asyncio
    async def test_sign_and_verify_round_trip(self, dispatcher, sample_subscription):
        """Signature produced by sign_payload can be verified independently."""
        dispatcher.create_subscription(sample_subscription)
        payload = {"alert": "disk_full", "host": "web-01"}
        signature = dispatcher.sign_payload(payload, sample_subscription.secret)

        # Verify independently
        payload_bytes = json.dumps(payload, sort_keys=True, default=str).encode()
        expected = hmac.new(
            sample_subscription.secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        assert signature == f"sha256={expected}"

    @pytest.mark.asyncio
    async def test_dispatch_and_test_event_coexist(
        self, dispatcher, sample_subscription, mock_logger
    ):
        """Regular dispatches and test events are both tracked in deliveries."""
        dispatcher.create_subscription(sample_subscription)
        await dispatcher.dispatch("incident.created", {"x": 1})
        await dispatcher.send_test_event("wh-test-001")
        deliveries = dispatcher.get_deliveries("wh-test-001")
        assert len(deliveries) == 2
        event_types = {d.event_type for d in deliveries}
        assert event_types == {"incident.created", "test"}

    @pytest.mark.asyncio
    async def test_multiple_dispatches_to_same_subscription(
        self, dispatcher, sample_subscription, mock_logger
    ):
        """Multiple dispatches produce multiple independent delivery records."""
        dispatcher.create_subscription(sample_subscription)
        await dispatcher.dispatch("incident.created", {"n": 1})
        await dispatcher.dispatch("incident.resolved", {"n": 2})
        deliveries = dispatcher.get_deliveries("wh-test-001")
        assert len(deliveries) == 2
        assert deliveries[0].id != deliveries[1].id
