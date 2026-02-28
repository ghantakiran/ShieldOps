"""Tests for shieldops.integrations.notifications.teams — MicrosoftTeamsNotifier."""

from __future__ import annotations

from shieldops.integrations.notifications.teams import (
    AdaptiveCardEntry,
    CardType,
    ChannelPriority,
    DeliveryOutcome,
    MicrosoftTeamsNotifier,
    TeamsMessageRecord,
    TeamsNotifierReport,
)


def _engine(**kw) -> MicrosoftTeamsNotifier:
    return MicrosoftTeamsNotifier(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # CardType (5)
    def test_card_alert(self):
        assert CardType.ALERT == "alert"

    def test_card_incident(self):
        assert CardType.INCIDENT == "incident"

    def test_card_deployment(self):
        assert CardType.DEPLOYMENT == "deployment"

    def test_card_compliance(self):
        assert CardType.COMPLIANCE == "compliance"

    def test_card_summary(self):
        assert CardType.SUMMARY == "summary"

    # ChannelPriority (5)
    def test_priority_urgent(self):
        assert ChannelPriority.URGENT == "urgent"

    def test_priority_high(self):
        assert ChannelPriority.HIGH == "high"

    def test_priority_normal(self):
        assert ChannelPriority.NORMAL == "normal"

    def test_priority_low(self):
        assert ChannelPriority.LOW == "low"

    def test_priority_informational(self):
        assert ChannelPriority.INFORMATIONAL == "informational"

    # DeliveryOutcome (5)
    def test_outcome_delivered(self):
        assert DeliveryOutcome.DELIVERED == "delivered"

    def test_outcome_failed(self):
        assert DeliveryOutcome.FAILED == "failed"

    def test_outcome_throttled(self):
        assert DeliveryOutcome.THROTTLED == "throttled"

    def test_outcome_channel_not_found(self):
        assert DeliveryOutcome.CHANNEL_NOT_FOUND == "channel_not_found"

    def test_outcome_retry_pending(self):
        assert DeliveryOutcome.RETRY_PENDING == "retry_pending"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_teams_message_record_defaults(self):
        r = TeamsMessageRecord()
        assert r.id
        assert r.channel_name == ""
        assert r.card_type == CardType.ALERT
        assert r.channel_priority == ChannelPriority.NORMAL
        assert r.delivery_outcome == DeliveryOutcome.DELIVERED
        assert r.message_size_bytes == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_adaptive_card_entry_defaults(self):
        r = AdaptiveCardEntry()
        assert r.id
        assert r.card_label == ""
        assert r.card_type == CardType.ALERT
        assert r.delivery_outcome == DeliveryOutcome.DELIVERED
        assert r.render_time_ms == 0.0
        assert r.created_at > 0

    def test_teams_notifier_report_defaults(self):
        r = TeamsNotifierReport()
        assert r.total_messages == 0
        assert r.total_cards == 0
        assert r.delivery_rate_pct == 0.0
        assert r.by_card_type == {}
        assert r.by_outcome == {}
        assert r.throttle_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_message
# -------------------------------------------------------------------


class TestRecordMessage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_message(
            "#sre-alerts",
            card_type=CardType.INCIDENT,
            delivery_outcome=DeliveryOutcome.DELIVERED,
        )
        assert r.channel_name == "#sre-alerts"
        assert r.card_type == CardType.INCIDENT

    def test_max_records_trim(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_message(f"#channel-{i}")
        assert len(eng._records) == 3

    def test_get_by_id(self):
        eng = _engine()
        r = eng.record_message("#sre-alerts")
        assert eng.get_message(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_message("nonexistent") is None

    def test_list_filter(self):
        eng = _engine()
        eng.record_message("#sre-alerts")
        eng.record_message("#deployments")
        results = eng.list_messages(channel_name="#sre-alerts")
        assert len(results) == 1

    def test_list_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_message(f"#channel-{i}")
        results = eng.list_messages(limit=3)
        assert len(results) == 3


# -------------------------------------------------------------------
# add_card
# -------------------------------------------------------------------


class TestAddCard:
    def test_basic(self):
        eng = _engine()
        r = eng.add_card(
            "incident-card",
            card_type=CardType.INCIDENT,
            delivery_outcome=DeliveryOutcome.DELIVERED,
            render_time_ms=45.2,
        )
        assert r.card_label == "incident-card"
        assert r.render_time_ms == 45.2

    def test_trim(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_card(f"card-{i}")
        assert len(eng._cards) == 2


# -------------------------------------------------------------------
# analyze_channel_delivery
# -------------------------------------------------------------------


class TestAnalyzeChannelDelivery:
    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_channel_delivery("#nonexistent")
        assert result["status"] == "no_data"

    def test_with_data(self):
        eng = _engine()
        eng.record_message("#sre-alerts", delivery_outcome=DeliveryOutcome.DELIVERED)
        eng.record_message("#sre-alerts", delivery_outcome=DeliveryOutcome.FAILED)
        result = eng.analyze_channel_delivery("#sre-alerts")
        assert result["channel_name"] == "#sre-alerts"
        assert result["total_messages"] == 2
        assert result["delivery_rate_pct"] == 50.0

    def test_meets_threshold(self):
        eng = _engine(max_retries=3)
        eng.record_message("#sre-alerts", delivery_outcome=DeliveryOutcome.DELIVERED)
        result = eng.analyze_channel_delivery("#sre-alerts")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_failed_notifications
# -------------------------------------------------------------------


class TestIdentifyFailedNotifications:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_notifications() == []

    def test_with_matches(self):
        eng = _engine()
        eng.record_message("#sre-alerts", delivery_outcome=DeliveryOutcome.FAILED)
        eng.record_message("#sre-alerts", delivery_outcome=DeliveryOutcome.FAILED)
        eng.record_message("#deployments", delivery_outcome=DeliveryOutcome.DELIVERED)
        results = eng.identify_failed_notifications()
        assert len(results) == 1
        assert results[0]["channel_name"] == "#sre-alerts"


# -------------------------------------------------------------------
# rank_by_channel_volume
# -------------------------------------------------------------------


class TestRankByChannelVolume:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_channel_volume() == []

    def test_ordering(self):
        eng = _engine()
        eng.record_message("#sre-alerts")
        eng.record_message("#sre-alerts")
        eng.record_message("#deployments")
        results = eng.rank_by_channel_volume()
        assert results[0]["channel_name"] == "#sre-alerts"
        assert results[0]["message_count"] == 2


# -------------------------------------------------------------------
# detect_throttling_patterns
# -------------------------------------------------------------------


class TestDetectThrottlingPatterns:
    def test_empty(self):
        eng = _engine()
        assert eng.detect_throttling_patterns() == []

    def test_detection(self):
        eng = _engine()
        for _ in range(5):
            eng.record_message("#sre-alerts", delivery_outcome=DeliveryOutcome.THROTTLED)
        eng.record_message("#deployments", delivery_outcome=DeliveryOutcome.DELIVERED)
        results = eng.detect_throttling_patterns()
        assert len(results) == 1
        assert results[0]["channel_name"] == "#sre-alerts"
        assert results[0]["throttling_detected"] is True


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_messages == 0
        assert "below" in report.recommendations[0]

    def test_with_data(self):
        eng = _engine()
        eng.record_message("#sre-alerts", delivery_outcome=DeliveryOutcome.DELIVERED)
        eng.record_message("#deployments", delivery_outcome=DeliveryOutcome.FAILED)
        eng.record_message("#deployments", delivery_outcome=DeliveryOutcome.FAILED)
        eng.add_card("card-1")
        report = eng.generate_report()
        assert report.total_messages == 3
        assert report.total_cards == 1
        assert report.by_card_type != {}
        assert report.recommendations != []

    def test_recommendations(self):
        eng = _engine()
        eng.record_message("#sre-alerts", delivery_outcome=DeliveryOutcome.DELIVERED)
        report = eng.generate_report()
        assert len(report.recommendations) >= 1


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clear(self):
        eng = _engine()
        eng.record_message("#sre-alerts")
        eng.add_card("card-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._cards) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_messages"] == 0
        assert stats["total_cards"] == 0
        assert stats["card_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_message("#sre-alerts", card_type=CardType.INCIDENT)
        eng.record_message("#deployments", card_type=CardType.DEPLOYMENT)
        eng.add_card("card-1")
        stats = eng.get_stats()
        assert stats["total_messages"] == 2
        assert stats["total_cards"] == 1
        assert stats["unique_channels"] == 2
