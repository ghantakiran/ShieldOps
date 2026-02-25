"""Tests for shieldops.incidents.comm_effectiveness — CommEffectivenessAnalyzer."""

from __future__ import annotations

import pytest

from shieldops.incidents.comm_effectiveness import (
    AudienceType,
    ChannelType,
    CommChannelMetrics,
    CommDeliveryRecord,
    CommEffectivenessAnalyzer,
    CommEffectivenessReport,
    DeliveryStatus,
)


def _engine(**kw) -> CommEffectivenessAnalyzer:
    return CommEffectivenessAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ChannelType (5)
    def test_channel_slack(self):
        assert ChannelType.SLACK == "slack"

    def test_channel_email(self):
        assert ChannelType.EMAIL == "email"

    def test_channel_pagerduty(self):
        assert ChannelType.PAGERDUTY == "pagerduty"

    def test_channel_sms(self):
        assert ChannelType.SMS == "sms"

    def test_channel_status_page(self):
        assert ChannelType.STATUS_PAGE == "status_page"

    # DeliveryStatus (5)
    def test_status_delivered(self):
        assert DeliveryStatus.DELIVERED == "delivered"

    def test_status_acknowledged(self):
        assert DeliveryStatus.ACKNOWLEDGED == "acknowledged"

    def test_status_missed(self):
        assert DeliveryStatus.MISSED == "missed"

    def test_status_delayed(self):
        assert DeliveryStatus.DELAYED == "delayed"

    def test_status_bounced(self):
        assert DeliveryStatus.BOUNCED == "bounced"

    # AudienceType (5)
    def test_audience_engineering(self):
        assert AudienceType.ENGINEERING == "engineering"

    def test_audience_management(self):
        assert AudienceType.MANAGEMENT == "management"

    def test_audience_customer(self):
        assert AudienceType.CUSTOMER == "customer"

    def test_audience_executive(self):
        assert AudienceType.EXECUTIVE == "executive"

    def test_audience_external(self):
        assert AudienceType.EXTERNAL == "external"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_comm_delivery_record_defaults(self):
        r = CommDeliveryRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.channel == ChannelType.SLACK
        assert r.audience == AudienceType.ENGINEERING
        assert r.status == DeliveryStatus.DELIVERED
        assert r.delivery_time_seconds == 0.0
        assert r.ack_time_seconds == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_comm_channel_metrics_defaults(self):
        r = CommChannelMetrics()
        assert r.id
        assert r.channel == ChannelType.SLACK
        assert r.delivery_rate_pct == 0.0
        assert r.avg_ack_time_seconds == 0.0
        assert r.total_sent == 0
        assert r.total_missed == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_comm_effectiveness_report_defaults(self):
        r = CommEffectivenessReport()
        assert r.total_deliveries == 0
        assert r.total_channel_metrics == 0
        assert r.avg_delivery_rate_pct == 0.0
        assert r.by_channel == {}
        assert r.by_status == {}
        assert r.underperforming_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_delivery
# -------------------------------------------------------------------


class TestRecordDelivery:
    def test_basic(self):
        eng = _engine()
        r = eng.record_delivery("INC-001", delivery_time_seconds=5.0, ack_time_seconds=30.0)
        assert r.incident_id == "INC-001"
        assert r.delivery_time_seconds == 5.0
        assert r.ack_time_seconds == 30.0

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_delivery(
            "INC-002",
            channel=ChannelType.EMAIL,
            audience=AudienceType.MANAGEMENT,
            status=DeliveryStatus.DELAYED,
            delivery_time_seconds=120.0,
            ack_time_seconds=300.0,
            details="email delayed",
        )
        assert r.channel == ChannelType.EMAIL
        assert r.audience == AudienceType.MANAGEMENT
        assert r.status == DeliveryStatus.DELAYED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_delivery(f"INC-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_delivery
# -------------------------------------------------------------------


class TestGetDelivery:
    def test_found(self):
        eng = _engine()
        r = eng.record_delivery("INC-001")
        assert eng.get_delivery(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_delivery("nonexistent") is None


# -------------------------------------------------------------------
# list_deliveries
# -------------------------------------------------------------------


class TestListDeliveries:
    def test_list_all(self):
        eng = _engine()
        eng.record_delivery("INC-001")
        eng.record_delivery("INC-002")
        assert len(eng.list_deliveries()) == 2

    def test_filter_by_incident_id(self):
        eng = _engine()
        eng.record_delivery("INC-001")
        eng.record_delivery("INC-002")
        results = eng.list_deliveries(incident_id="INC-001")
        assert len(results) == 1
        assert results[0].incident_id == "INC-001"

    def test_filter_by_channel(self):
        eng = _engine()
        eng.record_delivery("INC-001", channel=ChannelType.SLACK)
        eng.record_delivery("INC-002", channel=ChannelType.EMAIL)
        results = eng.list_deliveries(channel=ChannelType.SLACK)
        assert len(results) == 1
        assert results[0].incident_id == "INC-001"


# -------------------------------------------------------------------
# record_channel_metrics
# -------------------------------------------------------------------


class TestRecordChannelMetrics:
    def test_basic(self):
        eng = _engine()
        m = eng.record_channel_metrics(
            channel=ChannelType.SLACK,
            delivery_rate_pct=98.5,
            avg_ack_time_seconds=15.0,
            total_sent=200,
            total_missed=3,
        )
        assert m.channel == ChannelType.SLACK
        assert m.delivery_rate_pct == 98.5
        assert m.total_sent == 200

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(4):
            eng.record_channel_metrics(channel=ChannelType.SLACK)
        assert len(eng._channel_metrics) == 2


# -------------------------------------------------------------------
# analyze_channel_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeChannelEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_channel_metrics(
            channel=ChannelType.SLACK,
            delivery_rate_pct=97.0,
            avg_ack_time_seconds=12.5,
            total_sent=500,
            total_missed=15,
        )
        result = eng.analyze_channel_effectiveness(ChannelType.SLACK)
        assert result["channel"] == "slack"
        assert result["delivery_rate_pct"] == 97.0
        assert result["avg_ack_time_seconds"] == 12.5
        assert result["total_sent"] == 500
        assert result["total_missed"] == 15

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_channel_effectiveness(ChannelType.SMS)
        assert result["channel"] == "sms"
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_underperforming_channels
# -------------------------------------------------------------------


class TestIdentifyUnderperformingChannels:
    def test_with_underperforming(self):
        eng = _engine(min_delivery_rate_pct=95.0)
        eng.record_channel_metrics(channel=ChannelType.SLACK, delivery_rate_pct=98.0)
        eng.record_channel_metrics(channel=ChannelType.EMAIL, delivery_rate_pct=80.0)
        eng.record_channel_metrics(channel=ChannelType.SMS, delivery_rate_pct=70.0)
        results = eng.identify_underperforming_channels()
        assert len(results) == 2
        # Sorted by delivery_rate_pct ascending
        assert results[0]["channel"] == "sms"
        assert results[0]["gap_pct"] == pytest.approx(25.0)

    def test_empty(self):
        eng = _engine()
        assert eng.identify_underperforming_channels() == []


# -------------------------------------------------------------------
# rank_channels_by_ack_time
# -------------------------------------------------------------------


class TestRankChannelsByAckTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_channel_metrics(channel=ChannelType.SLACK, avg_ack_time_seconds=10.0)
        eng.record_channel_metrics(channel=ChannelType.EMAIL, avg_ack_time_seconds=60.0)
        eng.record_channel_metrics(channel=ChannelType.SMS, avg_ack_time_seconds=30.0)
        results = eng.rank_channels_by_ack_time()
        assert len(results) == 3
        assert results[0]["channel"] == "email"
        assert results[0]["avg_ack_time_seconds"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_channels_by_ack_time() == []


# -------------------------------------------------------------------
# detect_communication_gaps
# -------------------------------------------------------------------


class TestDetectCommunicationGaps:
    def test_with_gaps(self):
        eng = _engine()
        eng.record_delivery("INC-001", status=DeliveryStatus.DELIVERED)
        eng.record_delivery("INC-002", status=DeliveryStatus.MISSED)
        eng.record_delivery("INC-003", status=DeliveryStatus.BOUNCED)
        results = eng.detect_communication_gaps()
        assert len(results) == 2
        statuses = {r["status"] for r in results}
        assert statuses == {"missed", "bounced"}

    def test_empty(self):
        eng = _engine()
        assert eng.detect_communication_gaps() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_delivery_rate_pct=95.0)
        eng.record_delivery("INC-001", channel=ChannelType.SLACK)
        eng.record_delivery("INC-002", channel=ChannelType.EMAIL, status=DeliveryStatus.MISSED)
        eng.record_channel_metrics(channel=ChannelType.EMAIL, delivery_rate_pct=80.0)
        report = eng.generate_report()
        assert report.total_deliveries == 2
        assert report.total_channel_metrics == 1
        assert report.by_channel != {}
        assert report.by_status != {}
        assert report.underperforming_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_deliveries == 0
        assert report.avg_delivery_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_delivery("INC-001")
        eng.record_channel_metrics(channel=ChannelType.SLACK)
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._channel_metrics) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_deliveries"] == 0
        assert stats["total_channel_metrics"] == 0
        assert stats["channel_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_delivery("INC-001", channel=ChannelType.SLACK)
        eng.record_delivery("INC-002", channel=ChannelType.EMAIL)
        eng.record_channel_metrics(channel=ChannelType.SLACK)
        stats = eng.get_stats()
        assert stats["total_deliveries"] == 2
        assert stats["total_channel_metrics"] == 1
        assert stats["unique_incidents"] == 2
        assert stats["min_delivery_rate_pct"] == 95.0
