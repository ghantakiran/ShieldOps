"""Tests for webhook replay engine."""

from __future__ import annotations

from shieldops.integrations.outbound.replay_engine import (
    DeliveryStatus,
    ReplayResult,
    ReplayStatus,
    WebhookDelivery,
    WebhookReplayEngine,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _engine(**kwargs) -> WebhookReplayEngine:
    return WebhookReplayEngine(**kwargs)


def _record_failed(
    engine: WebhookReplayEngine,
    url: str = "https://example.com/hook",
    subscription_id: str = "sub-1",
) -> WebhookDelivery:
    return engine.record_delivery(
        url=url,
        event_type="alert",
        subscription_id=subscription_id,
        status=DeliveryStatus.FAILED,
        status_code=500,
        error="Internal Server Error",
    )


# ── Enum tests ───────────────────────────────────────────────────────


class TestDeliveryStatusEnum:
    def test_success(self) -> None:
        assert DeliveryStatus.SUCCESS == "success"

    def test_failed(self) -> None:
        assert DeliveryStatus.FAILED == "failed"

    def test_pending(self) -> None:
        assert DeliveryStatus.PENDING == "pending"

    def test_replaying(self) -> None:
        assert DeliveryStatus.REPLAYING == "replaying"

    def test_member_count(self) -> None:
        assert len(DeliveryStatus) == 4


class TestReplayStatusEnum:
    def test_completed(self) -> None:
        assert ReplayStatus.COMPLETED == "completed"

    def test_partial(self) -> None:
        assert ReplayStatus.PARTIAL == "partial"

    def test_failed(self) -> None:
        assert ReplayStatus.FAILED == "failed"

    def test_member_count(self) -> None:
        assert len(ReplayStatus) == 3


# ── Model tests ──────────────────────────────────────────────────────


class TestWebhookDeliveryModel:
    def test_defaults(self) -> None:
        d = WebhookDelivery(url="https://example.com/hook")
        assert len(d.id) == 12
        assert d.subscription_id == ""
        assert d.event_type == ""
        assert d.payload == {}
        assert d.status == DeliveryStatus.PENDING
        assert d.status_code == 0
        assert d.response_body == ""
        assert d.error == ""
        assert d.attempt_count == 0
        assert d.created_at > 0
        assert d.last_attempt_at is None
        assert d.metadata == {}


class TestReplayResultModel:
    def test_defaults(self) -> None:
        rr = ReplayResult()
        assert len(rr.id) == 12
        assert rr.status == ReplayStatus.COMPLETED
        assert rr.total == 0
        assert rr.succeeded == 0
        assert rr.failed == 0
        assert rr.results == []
        assert rr.started_at > 0
        assert rr.completed_at is None


# ── Engine creation ──────────────────────────────────────────────────


class TestEngineCreation:
    def test_default_params(self) -> None:
        e = _engine()
        assert e._max_retries == 3
        assert e._max_deliveries == 50000

    def test_custom_max_retries(self) -> None:
        e = _engine(max_retries=5)
        assert e._max_retries == 5

    def test_custom_max_deliveries(self) -> None:
        e = _engine(max_deliveries=100)
        assert e._max_deliveries == 100


# ── record_delivery ──────────────────────────────────────────────────


class TestRecordDelivery:
    def test_basic_recording(self) -> None:
        e = _engine()
        d = e.record_delivery(url="https://example.com/hook", event_type="alert")
        assert isinstance(d, WebhookDelivery)
        assert d.url == "https://example.com/hook"
        assert d.event_type == "alert"

    def test_success_status(self) -> None:
        e = _engine()
        d = e.record_delivery(
            url="https://example.com/hook",
            status=DeliveryStatus.SUCCESS,
            status_code=200,
        )
        assert d.status == DeliveryStatus.SUCCESS
        assert d.attempt_count == 1
        assert d.last_attempt_at is not None

    def test_failed_status(self) -> None:
        e = _engine()
        d = _record_failed(e)
        assert d.status == DeliveryStatus.FAILED
        assert d.attempt_count == 1
        assert d.last_attempt_at is not None

    def test_pending_status_defaults(self) -> None:
        e = _engine()
        d = e.record_delivery(url="https://example.com/hook")
        assert d.status == DeliveryStatus.PENDING
        assert d.attempt_count == 0
        assert d.last_attempt_at is None

    def test_auto_cleanup_at_max(self) -> None:
        e = _engine(max_deliveries=5)
        for i in range(6):
            e.record_delivery(url=f"https://example.com/hook/{i}", event_type="alert")
        # After cleanup, should be reduced (max_deliveries // 2 = 2 remain, then one added)
        assert len(e._deliveries) <= 5

    def test_stored_in_internal_dict(self) -> None:
        e = _engine()
        d = e.record_delivery(url="https://example.com/hook")
        assert d.id in e._deliveries

    def test_with_payload_and_metadata(self) -> None:
        e = _engine()
        d = e.record_delivery(
            url="https://example.com/hook",
            payload={"alert_id": "abc"},
            metadata={"source": "pagerduty"},
        )
        assert d.payload["alert_id"] == "abc"
        assert d.metadata["source"] == "pagerduty"


# ── get_delivery ─────────────────────────────────────────────────────


class TestGetDelivery:
    def test_found(self) -> None:
        e = _engine()
        d = e.record_delivery(url="https://example.com/hook")
        fetched = e.get_delivery(d.id)
        assert fetched is not None
        assert fetched.id == d.id

    def test_not_found(self) -> None:
        e = _engine()
        assert e.get_delivery("nonexistent") is None


# ── get_failed_deliveries ────────────────────────────────────────────


class TestGetFailedDeliveries:
    def test_returns_only_failed(self) -> None:
        e = _engine()
        _record_failed(e)
        e.record_delivery(url="https://example.com/hook", status=DeliveryStatus.SUCCESS)
        failed = e.get_failed_deliveries()
        assert len(failed) == 1
        assert failed[0].status == DeliveryStatus.FAILED

    def test_filter_by_subscription_id(self) -> None:
        e = _engine()
        _record_failed(e, subscription_id="sub-1")
        _record_failed(e, subscription_id="sub-2")
        result = e.get_failed_deliveries(subscription_id="sub-1")
        assert len(result) == 1
        assert result[0].subscription_id == "sub-1"

    def test_limit(self) -> None:
        e = _engine()
        for _ in range(5):
            _record_failed(e)
        result = e.get_failed_deliveries(limit=3)
        assert len(result) == 3

    def test_empty_when_no_failures(self) -> None:
        e = _engine()
        e.record_delivery(url="https://example.com/hook", status=DeliveryStatus.SUCCESS)
        assert e.get_failed_deliveries() == []


# ── replay_delivery ──────────────────────────────────────────────────


class TestReplayDelivery:
    def test_success_replay(self) -> None:
        e = _engine()
        d = _record_failed(e)
        result = e.replay_delivery(d.id, simulate_success=True)
        assert result is not None
        assert result.status == DeliveryStatus.SUCCESS
        assert result.status_code == 200
        assert result.error == ""

    def test_failed_replay(self) -> None:
        e = _engine()
        d = _record_failed(e)
        result = e.replay_delivery(d.id, simulate_success=False)
        assert result is not None
        assert result.status == DeliveryStatus.FAILED
        assert result.status_code == 500
        assert result.error == "Simulated failure"

    def test_not_found(self) -> None:
        e = _engine()
        result = e.replay_delivery("nonexistent")
        assert result is None

    def test_max_retries_exceeded(self) -> None:
        e = _engine(max_retries=2)
        d = _record_failed(e)
        # attempt_count is already 1 from record_delivery (FAILED)
        e.replay_delivery(d.id, simulate_success=False)  # attempt_count -> 2
        # Now at max retries; next replay should return delivery without incrementing
        before_count = d.attempt_count
        result = e.replay_delivery(d.id)
        assert result is not None
        assert result.attempt_count == before_count  # unchanged

    def test_attempt_count_increments(self) -> None:
        e = _engine(max_retries=5)
        d = _record_failed(e)
        initial = d.attempt_count  # 1
        e.replay_delivery(d.id, simulate_success=True)
        assert d.attempt_count == initial + 1

    def test_last_attempt_at_updates(self) -> None:
        e = _engine()
        d = _record_failed(e)
        old_attempt = d.last_attempt_at
        e.replay_delivery(d.id, simulate_success=True)
        assert d.last_attempt_at is not None
        assert d.last_attempt_at >= old_attempt


# ── replay_batch ─────────────────────────────────────────────────────


class TestReplayBatch:
    def test_all_success(self) -> None:
        e = _engine()
        d1 = _record_failed(e)
        d2 = _record_failed(e)
        result = e.replay_batch([d1.id, d2.id], simulate_success=True)
        assert result.status == ReplayStatus.COMPLETED
        assert result.total == 2
        assert result.succeeded == 2
        assert result.failed == 0
        assert result.completed_at is not None

    def test_all_fail(self) -> None:
        e = _engine()
        # Use IDs that don't exist
        result = e.replay_batch(["fake-1", "fake-2"], simulate_success=True)
        assert result.status == ReplayStatus.FAILED
        assert result.total == 2
        assert result.succeeded == 0
        assert result.failed == 2

    def test_partial_success(self) -> None:
        e = _engine()
        d = _record_failed(e)
        result = e.replay_batch([d.id, "nonexistent"], simulate_success=True)
        assert result.status == ReplayStatus.PARTIAL
        assert result.succeeded == 1
        assert result.failed == 1

    def test_empty_list(self) -> None:
        e = _engine()
        result = e.replay_batch([])
        assert result.total == 0
        assert result.succeeded == 0
        assert result.failed == 0
        # 0 failed => COMPLETED
        assert result.status == ReplayStatus.COMPLETED

    def test_results_list_populated(self) -> None:
        e = _engine()
        d = _record_failed(e)
        result = e.replay_batch([d.id], simulate_success=True)
        assert len(result.results) == 1
        assert result.results[0]["delivery_id"] == d.id
        assert result.results[0]["status"] == "success"

    def test_batch_simulated_failure(self) -> None:
        e = _engine()
        d = _record_failed(e)
        result = e.replay_batch([d.id], simulate_success=False)
        assert result.failed == 1
        assert result.results[0]["status"] == "failed"


# ── get_stats ────────────────────────────────────────────────────────


class TestGetStats:
    def test_empty(self) -> None:
        e = _engine()
        stats = e.get_stats()
        assert stats["total_deliveries"] == 0
        assert stats["by_status"] == {}

    def test_with_deliveries(self) -> None:
        e = _engine()
        _record_failed(e)
        e.record_delivery(url="https://example.com/hook", status=DeliveryStatus.SUCCESS)
        e.record_delivery(url="https://example.com/hook")  # pending
        stats = e.get_stats()
        assert stats["total_deliveries"] == 3
        assert stats["by_status"]["failed"] == 1
        assert stats["by_status"]["success"] == 1
        assert stats["by_status"]["pending"] == 1

    def test_stats_after_replay(self) -> None:
        e = _engine()
        d = _record_failed(e)
        e.replay_delivery(d.id, simulate_success=True)
        stats = e.get_stats()
        # Delivery status changed to SUCCESS after replay
        assert stats["by_status"]["success"] == 1
