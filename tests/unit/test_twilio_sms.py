"""Tests for shieldops.integrations.notifications.twilio_sms — TwilioSMSGateway."""

from __future__ import annotations

from shieldops.integrations.notifications.twilio_sms import (
    DeliveryReceipt,
    DeliveryStatus,
    MessageType,
    SMSPriority,
    SMSRecord,
    TwilioSMSGateway,
    TwilioSMSReport,
)


def _engine(**kw) -> TwilioSMSGateway:
    return TwilioSMSGateway(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # SMSPriority (5)
    def test_priority_critical(self):
        assert SMSPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert SMSPriority.HIGH == "high"

    def test_priority_medium(self):
        assert SMSPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert SMSPriority.LOW == "low"

    def test_priority_info(self):
        assert SMSPriority.INFO == "info"

    # DeliveryStatus (5)
    def test_status_delivered(self):
        assert DeliveryStatus.DELIVERED == "delivered"

    def test_status_pending(self):
        assert DeliveryStatus.PENDING == "pending"

    def test_status_failed(self):
        assert DeliveryStatus.FAILED == "failed"

    def test_status_bounced(self):
        assert DeliveryStatus.BOUNCED == "bounced"

    def test_status_opted_out(self):
        assert DeliveryStatus.OPTED_OUT == "opted_out"

    # MessageType (5)
    def test_type_alert(self):
        assert MessageType.ALERT == "alert"

    def test_type_acknowledgment(self):
        assert MessageType.ACKNOWLEDGMENT == "acknowledgment"

    def test_type_escalation(self):
        assert MessageType.ESCALATION == "escalation"

    def test_type_notification(self):
        assert MessageType.NOTIFICATION == "notification"

    def test_type_two_way(self):
        assert MessageType.TWO_WAY == "two_way"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_sms_record_defaults(self):
        r = SMSRecord()
        assert r.id
        assert r.recipient_number == ""
        assert r.priority == SMSPriority.MEDIUM
        assert r.delivery_status == DeliveryStatus.PENDING
        assert r.message_type == MessageType.ALERT
        assert r.character_count == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_delivery_receipt_defaults(self):
        r = DeliveryReceipt()
        assert r.id
        assert r.receipt_id == ""
        assert r.delivery_status == DeliveryStatus.PENDING
        assert r.message_type == MessageType.ALERT
        assert r.latency_ms == 0.0
        assert r.created_at > 0

    def test_twilio_sms_report_defaults(self):
        r = TwilioSMSReport()
        assert r.total_messages == 0
        assert r.total_receipts == 0
        assert r.delivery_rate_pct == 0.0
        assert r.by_priority == {}
        assert r.by_status == {}
        assert r.failed_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_message
# -------------------------------------------------------------------


class TestRecordMessage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_message(
            "+15551234567",
            priority=SMSPriority.HIGH,
            delivery_status=DeliveryStatus.DELIVERED,
        )
        assert r.recipient_number == "+15551234567"
        assert r.priority == SMSPriority.HIGH

    def test_max_records_trim(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_message(f"+1555000{i}")
        assert len(eng._records) == 3

    def test_get_by_id(self):
        eng = _engine()
        r = eng.record_message("+15551234567")
        assert eng.get_message(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_message("nonexistent") is None

    def test_list_filter(self):
        eng = _engine()
        eng.record_message("+15551111111")
        eng.record_message("+15552222222")
        results = eng.list_messages(recipient_number="+15551111111")
        assert len(results) == 1

    def test_list_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_message(f"+1555000{i}")
        results = eng.list_messages(limit=3)
        assert len(results) == 3


# -------------------------------------------------------------------
# add_receipt
# -------------------------------------------------------------------


class TestAddReceipt:
    def test_basic(self):
        eng = _engine()
        r = eng.add_receipt(
            "receipt-001",
            delivery_status=DeliveryStatus.DELIVERED,
            message_type=MessageType.ALERT,
            latency_ms=120.5,
        )
        assert r.receipt_id == "receipt-001"
        assert r.latency_ms == 120.5

    def test_trim(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_receipt(f"receipt-{i}")
        assert len(eng._receipts) == 2


# -------------------------------------------------------------------
# analyze_delivery_performance
# -------------------------------------------------------------------


class TestAnalyzeDeliveryPerformance:
    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_delivery_performance("+15559999999")
        assert result["status"] == "no_data"

    def test_with_data(self):
        eng = _engine()
        eng.record_message("+15551234567", delivery_status=DeliveryStatus.DELIVERED)
        eng.record_message("+15551234567", delivery_status=DeliveryStatus.FAILED)
        result = eng.analyze_delivery_performance("+15551234567")
        assert result["recipient_number"] == "+15551234567"
        assert result["total_messages"] == 2
        assert result["delivery_rate_pct"] == 50.0

    def test_meets_threshold(self):
        eng = _engine(max_retries=3)
        eng.record_message("+15551234567", delivery_status=DeliveryStatus.DELIVERED)
        result = eng.analyze_delivery_performance("+15551234567")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_failed_deliveries
# -------------------------------------------------------------------


class TestIdentifyFailedDeliveries:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_failed_deliveries() == []

    def test_with_matches(self):
        eng = _engine()
        eng.record_message("+15551234567", delivery_status=DeliveryStatus.FAILED)
        eng.record_message("+15551234567", delivery_status=DeliveryStatus.FAILED)
        eng.record_message("+15552222222", delivery_status=DeliveryStatus.DELIVERED)
        results = eng.identify_failed_deliveries()
        assert len(results) == 1
        assert results[0]["recipient_number"] == "+15551234567"


# -------------------------------------------------------------------
# rank_by_message_volume
# -------------------------------------------------------------------


class TestRankByMessageVolume:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_message_volume() == []

    def test_ordering(self):
        eng = _engine()
        eng.record_message("+15551234567")
        eng.record_message("+15551234567")
        eng.record_message("+15552222222")
        results = eng.rank_by_message_volume()
        assert results[0]["recipient_number"] == "+15551234567"
        assert results[0]["message_count"] == 2


# -------------------------------------------------------------------
# detect_opt_out_patterns
# -------------------------------------------------------------------


class TestDetectOptOutPatterns:
    def test_empty(self):
        eng = _engine()
        assert eng.detect_opt_out_patterns() == []

    def test_detection(self):
        eng = _engine()
        for _ in range(5):
            eng.record_message("+15551234567", delivery_status=DeliveryStatus.OPTED_OUT)
        eng.record_message("+15552222222", delivery_status=DeliveryStatus.DELIVERED)
        results = eng.detect_opt_out_patterns()
        assert len(results) == 1
        assert results[0]["recipient_number"] == "+15551234567"
        assert results[0]["opt_out_detected"] is True


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
        eng.record_message("+15551234567", delivery_status=DeliveryStatus.DELIVERED)
        eng.record_message("+15552222222", delivery_status=DeliveryStatus.FAILED)
        eng.record_message("+15552222222", delivery_status=DeliveryStatus.FAILED)
        eng.add_receipt("r-1")
        report = eng.generate_report()
        assert report.total_messages == 3
        assert report.total_receipts == 1
        assert report.by_priority != {}
        assert report.recommendations != []

    def test_recommendations(self):
        eng = _engine()
        eng.record_message("+15551234567", delivery_status=DeliveryStatus.DELIVERED)
        report = eng.generate_report()
        assert len(report.recommendations) >= 1


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clear(self):
        eng = _engine()
        eng.record_message("+15551234567")
        eng.add_receipt("r-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._receipts) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_messages"] == 0
        assert stats["total_receipts"] == 0
        assert stats["priority_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_message("+15551234567", priority=SMSPriority.CRITICAL)
        eng.record_message("+15552222222", priority=SMSPriority.LOW)
        eng.add_receipt("r-1")
        stats = eng.get_stats()
        assert stats["total_messages"] == 2
        assert stats["total_receipts"] == 1
        assert stats["unique_recipients"] == 2
