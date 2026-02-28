"""Tests for shieldops.integrations.notifications.twilio_voice — TwilioVoiceAlertSystem."""

from __future__ import annotations

from shieldops.integrations.notifications.twilio_voice import (
    CallPriority,
    CallStatus,
    IVRAction,
    IVRResponse,
    TwilioVoiceAlertSystem,
    TwilioVoiceReport,
    VoiceCallRecord,
)


def _engine(**kw) -> TwilioVoiceAlertSystem:
    return TwilioVoiceAlertSystem(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # CallPriority (5)
    def test_priority_critical(self):
        assert CallPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert CallPriority.HIGH == "high"

    def test_priority_medium(self):
        assert CallPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert CallPriority.LOW == "low"

    def test_priority_info(self):
        assert CallPriority.INFO == "info"

    # CallStatus (5)
    def test_status_completed(self):
        assert CallStatus.COMPLETED == "completed"

    def test_status_no_answer(self):
        assert CallStatus.NO_ANSWER == "no_answer"

    def test_status_busy(self):
        assert CallStatus.BUSY == "busy"

    def test_status_failed(self):
        assert CallStatus.FAILED == "failed"

    def test_status_escalated(self):
        assert CallStatus.ESCALATED == "escalated"

    # IVRAction (5)
    def test_ivr_acknowledge(self):
        assert IVRAction.ACKNOWLEDGE == "acknowledge"

    def test_ivr_escalate(self):
        assert IVRAction.ESCALATE == "escalate"

    def test_ivr_snooze(self):
        assert IVRAction.SNOOZE == "snooze"

    def test_ivr_reject(self):
        assert IVRAction.REJECT == "reject"

    def test_ivr_transfer(self):
        assert IVRAction.TRANSFER == "transfer"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_voice_call_record_defaults(self):
        r = VoiceCallRecord()
        assert r.id
        assert r.recipient_number == ""
        assert r.call_priority == CallPriority.HIGH
        assert r.call_status == CallStatus.COMPLETED
        assert r.ivr_action == IVRAction.ACKNOWLEDGE
        assert r.duration_seconds == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_ivr_response_defaults(self):
        r = IVRResponse()
        assert r.id
        assert r.response_label == ""
        assert r.ivr_action == IVRAction.ACKNOWLEDGE
        assert r.call_status == CallStatus.COMPLETED
        assert r.confidence_score == 0.0
        assert r.created_at > 0

    def test_twilio_voice_report_defaults(self):
        r = TwilioVoiceReport()
        assert r.total_calls == 0
        assert r.total_responses == 0
        assert r.answer_rate_pct == 0.0
        assert r.by_priority == {}
        assert r.by_status == {}
        assert r.escalation_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_call
# -------------------------------------------------------------------


class TestRecordCall:
    def test_basic(self):
        eng = _engine()
        r = eng.record_call(
            "+15551234567",
            call_priority=CallPriority.CRITICAL,
            call_status=CallStatus.COMPLETED,
        )
        assert r.recipient_number == "+15551234567"
        assert r.call_priority == CallPriority.CRITICAL

    def test_max_records_trim(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_call(f"+1555000{i}")
        assert len(eng._records) == 3

    def test_get_by_id(self):
        eng = _engine()
        r = eng.record_call("+15551234567")
        assert eng.get_call(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_call("nonexistent") is None

    def test_list_filter(self):
        eng = _engine()
        eng.record_call("+15551111111")
        eng.record_call("+15552222222")
        results = eng.list_calls(recipient_number="+15551111111")
        assert len(results) == 1

    def test_list_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_call(f"+1555000{i}")
        results = eng.list_calls(limit=3)
        assert len(results) == 3


# -------------------------------------------------------------------
# add_ivr_response
# -------------------------------------------------------------------


class TestAddIVRResponse:
    def test_basic(self):
        eng = _engine()
        r = eng.add_ivr_response(
            "ack-response",
            ivr_action=IVRAction.ACKNOWLEDGE,
            call_status=CallStatus.COMPLETED,
            confidence_score=0.95,
        )
        assert r.response_label == "ack-response"
        assert r.confidence_score == 0.95

    def test_trim(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_ivr_response(f"response-{i}")
        assert len(eng._responses) == 2


# -------------------------------------------------------------------
# analyze_answer_rates
# -------------------------------------------------------------------


class TestAnalyzeAnswerRates:
    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_answer_rates("+15559999999")
        assert result["status"] == "no_data"

    def test_with_data(self):
        eng = _engine()
        eng.record_call("+15551234567", call_status=CallStatus.COMPLETED)
        eng.record_call("+15551234567", call_status=CallStatus.NO_ANSWER)
        result = eng.analyze_answer_rates("+15551234567")
        assert result["recipient_number"] == "+15551234567"
        assert result["total_calls"] == 2
        assert result["answer_rate_pct"] == 50.0

    def test_meets_threshold(self):
        eng = _engine(max_ring_seconds=30)
        eng.record_call("+15551234567", call_status=CallStatus.COMPLETED)
        result = eng.analyze_answer_rates("+15551234567")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_unanswered_calls
# -------------------------------------------------------------------


class TestIdentifyUnansweredCalls:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_unanswered_calls() == []

    def test_with_matches(self):
        eng = _engine()
        eng.record_call("+15551234567", call_status=CallStatus.NO_ANSWER)
        eng.record_call("+15551234567", call_status=CallStatus.NO_ANSWER)
        eng.record_call("+15552222222", call_status=CallStatus.COMPLETED)
        results = eng.identify_unanswered_calls()
        assert len(results) == 1
        assert results[0]["recipient_number"] == "+15551234567"


# -------------------------------------------------------------------
# rank_by_call_volume
# -------------------------------------------------------------------


class TestRankByCallVolume:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_call_volume() == []

    def test_ordering(self):
        eng = _engine()
        eng.record_call("+15551234567")
        eng.record_call("+15551234567")
        eng.record_call("+15552222222")
        results = eng.rank_by_call_volume()
        assert results[0]["recipient_number"] == "+15551234567"
        assert results[0]["call_count"] == 2


# -------------------------------------------------------------------
# detect_escalation_patterns
# -------------------------------------------------------------------


class TestDetectEscalationPatterns:
    def test_empty(self):
        eng = _engine()
        assert eng.detect_escalation_patterns() == []

    def test_detection(self):
        eng = _engine()
        for _ in range(5):
            eng.record_call("+15551234567", call_status=CallStatus.ESCALATED)
        eng.record_call("+15552222222", call_status=CallStatus.COMPLETED)
        results = eng.detect_escalation_patterns()
        assert len(results) == 1
        assert results[0]["recipient_number"] == "+15551234567"
        assert results[0]["escalation_detected"] is True


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_calls == 0
        assert "below" in report.recommendations[0]

    def test_with_data(self):
        eng = _engine()
        eng.record_call("+15551234567", call_status=CallStatus.COMPLETED)
        eng.record_call("+15552222222", call_status=CallStatus.NO_ANSWER)
        eng.record_call("+15552222222", call_status=CallStatus.NO_ANSWER)
        eng.add_ivr_response("resp-1")
        report = eng.generate_report()
        assert report.total_calls == 3
        assert report.total_responses == 1
        assert report.by_priority != {}
        assert report.recommendations != []

    def test_recommendations(self):
        eng = _engine()
        eng.record_call("+15551234567", call_status=CallStatus.COMPLETED)
        report = eng.generate_report()
        assert len(report.recommendations) >= 1


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clear(self):
        eng = _engine()
        eng.record_call("+15551234567")
        eng.add_ivr_response("resp-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._responses) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_calls"] == 0
        assert stats["total_responses"] == 0
        assert stats["priority_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_call("+15551234567", call_priority=CallPriority.CRITICAL)
        eng.record_call("+15552222222", call_priority=CallPriority.LOW)
        eng.add_ivr_response("resp-1")
        stats = eng.get_stats()
        assert stats["total_calls"] == 2
        assert stats["total_responses"] == 1
        assert stats["unique_recipients"] == 2
