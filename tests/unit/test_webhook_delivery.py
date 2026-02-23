"""Comprehensive unit tests for webhook delivery engine (Phase 13 F7).

Tests cover:
- DeliveryAttempt Pydantic model defaults and custom fields
- WebhookDeliveryEngine initialization and defaults
- WebhookDeliveryEngine.deliver (httpx ImportError path = simulated success)
- OutboundWebhookDispatcher with delivery engine integration
- Dispatch to matching subscriptions via delivery engine
- HMAC-SHA256 signing with X-Signature-256 header
- Dead letter queue on delivery failure
- Subscription CRUD via dispatcher
- Test event delivery
- DeliveryRecord status tracking (PENDING, DELIVERED, FAILED)
- Edge cases: no subscriptions, empty payload, unknown subscription

Requires: pytest, pytest-asyncio
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from shieldops.integrations.outbound.webhook_dispatcher import (
    DeliveryAttempt,
    DeliveryRecord,
    DeliveryStatus,
    OutboundWebhookDispatcher,
    WebhookDeliveryEngine,
    WebhookSubscription,
)

# Patch target for the structlog logger.
_LOGGER_PATCH = "shieldops.integrations.outbound.webhook_dispatcher.logger"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> WebhookDeliveryEngine:
    """Fresh delivery engine with default settings."""
    return WebhookDeliveryEngine()


@pytest.fixture
def success_engine() -> AsyncMock:
    """A mock delivery engine that always returns a successful attempt."""
    mock_eng = AsyncMock(spec=WebhookDeliveryEngine)
    mock_eng.max_attempts = 3
    mock_eng.timeout = 10.0

    async def _deliver(url, payload, headers=None):
        return [DeliveryAttempt(attempt=1, status_code=200, response_time_ms=1.0)]

    mock_eng.deliver = AsyncMock(side_effect=_deliver)
    return mock_eng


@pytest.fixture
def dispatcher(success_engine) -> OutboundWebhookDispatcher:
    """Dispatcher with a mock engine that always succeeds (no real HTTP)."""
    return OutboundWebhookDispatcher(delivery_engine=success_engine)


@pytest.fixture
def mock_logger():
    """Patch module-level structlog logger."""
    with patch(_LOGGER_PATCH) as mock_log:
        yield mock_log


@pytest.fixture
def sample_subscription() -> WebhookSubscription:
    return WebhookSubscription(
        id="wh-delivery-001",
        url="https://hooks.example.com/test",
        events=["incident.created", "incident.resolved"],
        secret="test-secret-key",
        description="Delivery test hook",
    )


@pytest.fixture
def wildcard_subscription() -> WebhookSubscription:
    return WebhookSubscription(
        id="wh-wildcard",
        url="https://hooks.example.com/all",
        events=[],
        secret="wildcard-secret",
    )


@pytest.fixture
def sample_payload() -> dict:
    return {"incident_id": "inc-abc", "severity": "high"}


# ===========================================================================
# DeliveryAttempt Model Tests
# ===========================================================================


class TestDeliveryAttemptModel:
    """Tests for the DeliveryAttempt Pydantic model."""

    def test_default_attempt_is_one(self):
        attempt = DeliveryAttempt()
        assert attempt.attempt == 1

    def test_default_status_code_is_none(self):
        attempt = DeliveryAttempt()
        assert attempt.status_code is None

    def test_default_response_time_ms_zero(self):
        attempt = DeliveryAttempt()
        assert attempt.response_time_ms == 0.0

    def test_default_error_is_none(self):
        attempt = DeliveryAttempt()
        assert attempt.error is None

    def test_timestamp_is_datetime(self):
        attempt = DeliveryAttempt()
        assert isinstance(attempt.timestamp, datetime)

    def test_custom_attempt_number(self):
        attempt = DeliveryAttempt(attempt=3)
        assert attempt.attempt == 3

    def test_custom_status_code(self):
        attempt = DeliveryAttempt(status_code=200)
        assert attempt.status_code == 200

    def test_custom_response_time(self):
        attempt = DeliveryAttempt(response_time_ms=42.5)
        assert attempt.response_time_ms == 42.5

    def test_custom_error_message(self):
        attempt = DeliveryAttempt(error="Connection timeout")
        assert attempt.error == "Connection timeout"


# ===========================================================================
# WebhookDeliveryEngine Initialization Tests
# ===========================================================================


class TestWebhookDeliveryEngineInit:
    """Tests for WebhookDeliveryEngine constructor and class attributes."""

    def test_default_max_attempts(self):
        engine = WebhookDeliveryEngine()
        assert engine.max_attempts == 3

    def test_default_timeout(self):
        engine = WebhookDeliveryEngine()
        assert engine.timeout == 10.0

    def test_custom_max_attempts(self):
        engine = WebhookDeliveryEngine(max_attempts=5)
        assert engine.max_attempts == 5

    def test_custom_timeout(self):
        engine = WebhookDeliveryEngine(timeout=30.0)
        assert engine.timeout == 30.0

    def test_class_default_timeout_constant(self):
        assert WebhookDeliveryEngine.DEFAULT_TIMEOUT == 10.0

    def test_class_backoff_base_constant(self):
        assert WebhookDeliveryEngine.BACKOFF_BASE == 1.0

    def test_class_backoff_factor_constant(self):
        assert WebhookDeliveryEngine.BACKOFF_FACTOR == 4.0


# ===========================================================================
# WebhookDeliveryEngine.deliver Tests (httpx ImportError = simulated success)
# ===========================================================================


class TestWebhookDeliveryEngineDeliver:
    """Tests for WebhookDeliveryEngine.deliver.

    We hide httpx via sys.modules patching so the engine triggers
    the ImportError fallback (simulated success) path.
    """

    @pytest.fixture(autouse=True)
    def _hide_httpx(self, monkeypatch):
        """Force the ImportError path inside deliver() by hiding httpx."""
        import sys

        monkeypatch.setitem(sys.modules, "httpx", None)

    @pytest.mark.asyncio
    async def test_deliver_returns_list_of_attempts(self, engine):
        attempts = await engine.deliver(
            url="https://example.com/hook",
            payload={"event": "test"},
        )
        assert isinstance(attempts, list)
        assert len(attempts) >= 1

    @pytest.mark.asyncio
    async def test_deliver_simulated_success_status_200(self, engine):
        attempts = await engine.deliver(
            url="https://example.com/hook",
            payload={"event": "test"},
        )
        last = attempts[-1]
        assert last.status_code == 200

    @pytest.mark.asyncio
    async def test_deliver_single_attempt_on_simulated_success(self, engine):
        attempts = await engine.deliver(
            url="https://example.com/hook",
            payload={"event": "test"},
        )
        # Simulated success returns after first attempt
        assert len(attempts) == 1
        assert attempts[0].attempt == 1

    @pytest.mark.asyncio
    async def test_deliver_response_time_non_negative(self, engine):
        attempts = await engine.deliver(
            url="https://example.com/hook",
            payload={"event": "test"},
        )
        assert attempts[0].response_time_ms >= 0

    @pytest.mark.asyncio
    async def test_deliver_with_headers(self, engine):
        attempts = await engine.deliver(
            url="https://example.com/hook",
            payload={"event": "test"},
            headers={"X-Signature-256": "sha256=abc123"},
        )
        assert len(attempts) >= 1

    @pytest.mark.asyncio
    async def test_deliver_error_is_none_on_success(self, engine):
        attempts = await engine.deliver(
            url="https://example.com/hook",
            payload={"event": "test"},
        )
        assert attempts[0].error is None

    @pytest.mark.asyncio
    async def test_deliver_empty_payload(self, engine):
        attempts = await engine.deliver(
            url="https://example.com/hook",
            payload={},
        )
        assert attempts[0].status_code == 200


# ===========================================================================
# OutboundWebhookDispatcher with Delivery Engine Tests
# ===========================================================================


class TestDispatcherWithEngine:
    """Tests for OutboundWebhookDispatcher using the delivery engine."""

    def test_dispatcher_uses_default_engine(self):
        d = OutboundWebhookDispatcher()
        assert isinstance(d._engine, WebhookDeliveryEngine)

    def test_dispatcher_accepts_custom_engine(self):
        custom_engine = WebhookDeliveryEngine(max_attempts=5, timeout=30.0)
        d = OutboundWebhookDispatcher(delivery_engine=custom_engine)
        assert d._engine is custom_engine
        assert d._engine.max_attempts == 5

    @pytest.mark.asyncio
    async def test_dispatch_uses_engine_for_delivery(
        self, dispatcher, sample_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("incident.created", sample_payload)
        assert len(records) == 1
        assert records[0].status == DeliveryStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_dispatch_sets_delivered_at(
        self, dispatcher, sample_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("incident.created", sample_payload)
        assert records[0].delivered_at is not None

    @pytest.mark.asyncio
    async def test_dispatch_sets_status_code_200(
        self, dispatcher, sample_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("incident.created", sample_payload)
        assert records[0].status_code == 200


# ===========================================================================
# HMAC-SHA256 Signing Integration Tests
# ===========================================================================


class TestSigningIntegration:
    """Tests for HMAC-SHA256 signing in the dispatch flow."""

    def test_sign_payload_returns_sha256_prefix(self, dispatcher):
        sig = dispatcher.sign_payload({"key": "value"}, "secret")
        assert sig.startswith("sha256=")

    def test_sign_payload_hex_length(self, dispatcher):
        sig = dispatcher.sign_payload({"key": "value"}, "secret")
        hex_part = sig.removeprefix("sha256=")
        assert len(hex_part) == 64

    def test_sign_payload_deterministic(self, dispatcher):
        payload = {"a": 1, "b": 2}
        sig1 = dispatcher.sign_payload(payload, "secret")
        sig2 = dispatcher.sign_payload(payload, "secret")
        assert sig1 == sig2

    def test_sign_payload_different_secrets_differ(self, dispatcher):
        payload = {"key": "value"}
        sig1 = dispatcher.sign_payload(payload, "secret-a")
        sig2 = dispatcher.sign_payload(payload, "secret-b")
        assert sig1 != sig2

    def test_sign_payload_matches_manual_hmac(self, dispatcher):
        payload = {"event": "test", "count": 42}
        secret = "my-secret"  # noqa: S105
        expected_bytes = json.dumps(payload, sort_keys=True, default=str).encode()
        expected_sig = hmac.new(secret.encode(), expected_bytes, hashlib.sha256).hexdigest()
        result = dispatcher.sign_payload(payload, secret)
        assert result == f"sha256={expected_sig}"

    def test_sign_payload_key_order_independent(self, dispatcher):
        sig1 = dispatcher.sign_payload({"z": 1, "a": 2}, "secret")
        sig2 = dispatcher.sign_payload({"a": 2, "z": 1}, "secret")
        assert sig1 == sig2


# ===========================================================================
# Dead Letter Queue Tests
# ===========================================================================


class TestDeadLetterQueue:
    """Tests for dead letter queue behavior on failed delivery."""

    def test_dead_letters_initially_empty(self, dispatcher):
        assert dispatcher.dead_letters == []

    @pytest.mark.asyncio
    async def test_dead_letter_on_failed_delivery(self, sample_subscription, mock_logger):
        """When delivery engine returns non-2xx, record goes to dead letters."""
        # Create a mock engine that returns a failed attempt
        mock_engine = AsyncMock()
        failed_attempt = DeliveryAttempt(attempt=3, status_code=500, error="HTTP 500")
        mock_engine.deliver = AsyncMock(return_value=[failed_attempt])

        dispatcher = OutboundWebhookDispatcher(delivery_engine=mock_engine)
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("incident.created", {"x": 1})
        assert len(records) == 1
        assert records[0].status == DeliveryStatus.FAILED
        assert len(dispatcher.dead_letters) == 1

    @pytest.mark.asyncio
    async def test_dead_letter_preserves_error_message(self, sample_subscription, mock_logger):
        mock_engine = AsyncMock()
        failed_attempt = DeliveryAttempt(attempt=1, status_code=503, error="HTTP 503")
        mock_engine.deliver = AsyncMock(return_value=[failed_attempt])

        dispatcher = OutboundWebhookDispatcher(delivery_engine=mock_engine)
        dispatcher.create_subscription(sample_subscription)
        await dispatcher.dispatch("incident.created", {"x": 1})
        assert dispatcher.dead_letters[0].error == "HTTP 503"

    @pytest.mark.asyncio
    async def test_dead_letter_on_empty_attempts(self, sample_subscription, mock_logger):
        """When engine returns empty list, record goes to dead letters."""
        mock_engine = AsyncMock()
        mock_engine.deliver = AsyncMock(return_value=[])

        dispatcher = OutboundWebhookDispatcher(delivery_engine=mock_engine)
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("incident.created", {"x": 1})
        assert records[0].status == DeliveryStatus.FAILED
        assert records[0].error == "No delivery attempts"
        assert len(dispatcher.dead_letters) == 1

    @pytest.mark.asyncio
    async def test_successful_delivery_not_in_dead_letters(
        self, dispatcher, sample_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        await dispatcher.dispatch("incident.created", sample_payload)
        assert len(dispatcher.dead_letters) == 0


# ===========================================================================
# Subscription CRUD Tests
# ===========================================================================


class TestSubscriptionCRUD:
    """Tests for subscription create, read, update, delete."""

    def test_create_subscription(self, dispatcher, sample_subscription):
        result = dispatcher.create_subscription(sample_subscription)
        assert result.id == "wh-delivery-001"

    def test_get_subscription(self, dispatcher, sample_subscription):
        dispatcher.create_subscription(sample_subscription)
        fetched = dispatcher.get_subscription("wh-delivery-001")
        assert fetched is not None
        assert fetched.url == "https://hooks.example.com/test"

    def test_get_subscription_not_found(self, dispatcher):
        assert dispatcher.get_subscription("nonexistent") is None

    def test_list_subscriptions(self, dispatcher, sample_subscription, wildcard_subscription):
        dispatcher.create_subscription(sample_subscription)
        dispatcher.create_subscription(wildcard_subscription)
        subs = dispatcher.list_subscriptions()
        assert len(subs) == 2

    def test_delete_subscription(self, dispatcher, sample_subscription):
        dispatcher.create_subscription(sample_subscription)
        assert dispatcher.delete_subscription("wh-delivery-001") is True
        assert dispatcher.get_subscription("wh-delivery-001") is None

    def test_delete_nonexistent_subscription(self, dispatcher):
        assert dispatcher.delete_subscription("no-such-id") is False

    def test_list_subscriptions_empty(self, dispatcher):
        assert dispatcher.list_subscriptions() == []


# ===========================================================================
# Test Event Delivery Tests
# ===========================================================================


class TestSendTestEvent:
    """Tests for send_test_event."""

    @pytest.mark.asyncio
    async def test_send_test_event_returns_record(
        self, dispatcher, sample_subscription, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        record = await dispatcher.send_test_event("wh-delivery-001")
        assert record is not None
        assert isinstance(record, DeliveryRecord)

    @pytest.mark.asyncio
    async def test_send_test_event_type_is_test(self, dispatcher, sample_subscription, mock_logger):
        dispatcher.create_subscription(sample_subscription)
        record = await dispatcher.send_test_event("wh-delivery-001")
        assert record.event_type == "test"

    @pytest.mark.asyncio
    async def test_send_test_event_payload_has_message(
        self, dispatcher, sample_subscription, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        record = await dispatcher.send_test_event("wh-delivery-001")
        data = record.payload["data"]
        assert "ShieldOps" in data["message"]

    @pytest.mark.asyncio
    async def test_send_test_event_unknown_returns_none(self, dispatcher, mock_logger):
        result = await dispatcher.send_test_event("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_send_test_event_stored_in_deliveries(
        self, dispatcher, sample_subscription, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        await dispatcher.send_test_event("wh-delivery-001")
        deliveries = dispatcher.get_deliveries("wh-delivery-001")
        assert len(deliveries) == 1


# ===========================================================================
# DeliveryRecord Status Tracking Tests
# ===========================================================================


class TestDeliveryRecordTracking:
    """Tests for DeliveryRecord status and field tracking."""

    def test_record_default_status_pending(self):
        record = DeliveryRecord(subscription_id="wh-1", event_type="test")
        assert record.status == DeliveryStatus.PENDING

    def test_record_id_prefix(self):
        record = DeliveryRecord(subscription_id="wh-1", event_type="test")
        assert record.id.startswith("dlv-")

    def test_record_id_uniqueness(self):
        ids = {DeliveryRecord(subscription_id="wh-1", event_type="t").id for _ in range(50)}
        assert len(ids) == 50

    @pytest.mark.asyncio
    async def test_delivered_record_status(
        self, dispatcher, sample_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("incident.created", sample_payload)
        assert records[0].status == DeliveryStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_record_attempt_count(
        self, dispatcher, sample_subscription, sample_payload, mock_logger
    ):
        dispatcher.create_subscription(sample_subscription)
        records = await dispatcher.dispatch("incident.created", sample_payload)
        # Simulated success returns after 1 attempt
        assert records[0].attempt == 1

    @pytest.mark.asyncio
    async def test_get_deliveries_filters_by_subscription(self, dispatcher, mock_logger):
        sub_a = WebhookSubscription(id="wh-a", url="https://a.com", events=[])
        sub_b = WebhookSubscription(id="wh-b", url="https://b.com", events=[])
        dispatcher.create_subscription(sub_a)
        dispatcher.create_subscription(sub_b)
        await dispatcher.dispatch("incident.created", {"x": 1})
        assert len(dispatcher.get_deliveries("wh-a")) == 1
        assert len(dispatcher.get_deliveries("wh-b")) == 1

    def test_get_deliveries_empty_for_new_subscription(self, dispatcher, sample_subscription):
        dispatcher.create_subscription(sample_subscription)
        assert dispatcher.get_deliveries("wh-delivery-001") == []
