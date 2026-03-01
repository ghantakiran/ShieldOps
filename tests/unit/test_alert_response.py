"""Tests for shieldops.analytics.alert_response — AlertResponseAnalyzer."""

from __future__ import annotations

from shieldops.analytics.alert_response import (
    AlertOutcome,
    AlertResponseAnalyzer,
    AlertResponseRecord,
    AlertResponseReport,
    ResponseAction,
    ResponseMetric,
    ResponseSpeed,
)


def _engine(**kw) -> AlertResponseAnalyzer:
    return AlertResponseAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_response_action_acknowledged(self):
        assert ResponseAction.ACKNOWLEDGED == "acknowledged"

    def test_response_action_investigated(self):
        assert ResponseAction.INVESTIGATED == "investigated"

    def test_response_action_escalated(self):
        assert ResponseAction.ESCALATED == "escalated"

    def test_response_action_resolved(self):
        assert ResponseAction.RESOLVED == "resolved"

    def test_response_action_suppressed(self):
        assert ResponseAction.SUPPRESSED == "suppressed"

    def test_response_speed_immediate(self):
        assert ResponseSpeed.IMMEDIATE == "immediate"

    def test_response_speed_fast(self):
        assert ResponseSpeed.FAST == "fast"

    def test_response_speed_normal(self):
        assert ResponseSpeed.NORMAL == "normal"

    def test_response_speed_slow(self):
        assert ResponseSpeed.SLOW == "slow"

    def test_response_speed_missed(self):
        assert ResponseSpeed.MISSED == "missed"

    def test_alert_outcome_true_positive(self):
        assert AlertOutcome.TRUE_POSITIVE == "true_positive"

    def test_alert_outcome_false_positive(self):
        assert AlertOutcome.FALSE_POSITIVE == "false_positive"

    def test_alert_outcome_noise(self):
        assert AlertOutcome.NOISE == "noise"

    def test_alert_outcome_duplicate(self):
        assert AlertOutcome.DUPLICATE == "duplicate"

    def test_alert_outcome_informational(self):
        assert AlertOutcome.INFORMATIONAL == "informational"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_alert_response_record_defaults(self):
        r = AlertResponseRecord()
        assert r.id
        assert r.alert_id == ""
        assert r.response_action == ResponseAction.ACKNOWLEDGED
        assert r.response_speed == ResponseSpeed.NORMAL
        assert r.alert_outcome == AlertOutcome.TRUE_POSITIVE
        assert r.response_time_minutes == 0.0
        assert r.responder == ""
        assert r.created_at > 0

    def test_response_metric_defaults(self):
        m = ResponseMetric()
        assert m.id
        assert m.metric_name == ""
        assert m.response_action == ResponseAction.ACKNOWLEDGED
        assert m.avg_response_time == 0.0
        assert m.total_responses == 0
        assert m.description == ""
        assert m.created_at > 0

    def test_alert_response_report_defaults(self):
        r = AlertResponseReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.measured_responders == 0
        assert r.avg_response_time_minutes == 0.0
        assert r.by_action == {}
        assert r.by_speed == {}
        assert r.by_outcome == {}
        assert r.slow_alerts == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_response
# ---------------------------------------------------------------------------


class TestRecordResponse:
    def test_basic(self):
        eng = _engine()
        r = eng.record_response(
            alert_id="alert-001",
            response_action=ResponseAction.RESOLVED,
            response_speed=ResponseSpeed.FAST,
            alert_outcome=AlertOutcome.TRUE_POSITIVE,
            response_time_minutes=5.0,
            responder="alice",
        )
        assert r.alert_id == "alert-001"
        assert r.response_action == ResponseAction.RESOLVED
        assert r.response_speed == ResponseSpeed.FAST
        assert r.alert_outcome == AlertOutcome.TRUE_POSITIVE
        assert r.response_time_minutes == 5.0
        assert r.responder == "alice"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_response(alert_id=f"alert-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_response
# ---------------------------------------------------------------------------


class TestGetResponse:
    def test_found(self):
        eng = _engine()
        r = eng.record_response(
            alert_id="alert-001",
            response_action=ResponseAction.ESCALATED,
        )
        result = eng.get_response(r.id)
        assert result is not None
        assert result.response_action == ResponseAction.ESCALATED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_response("nonexistent") is None


# ---------------------------------------------------------------------------
# list_responses
# ---------------------------------------------------------------------------


class TestListResponses:
    def test_list_all(self):
        eng = _engine()
        eng.record_response(alert_id="alert-001")
        eng.record_response(alert_id="alert-002")
        assert len(eng.list_responses()) == 2

    def test_filter_by_response_action(self):
        eng = _engine()
        eng.record_response(
            alert_id="alert-001",
            response_action=ResponseAction.ACKNOWLEDGED,
        )
        eng.record_response(
            alert_id="alert-002",
            response_action=ResponseAction.ESCALATED,
        )
        results = eng.list_responses(response_action=ResponseAction.ACKNOWLEDGED)
        assert len(results) == 1

    def test_filter_by_response_speed(self):
        eng = _engine()
        eng.record_response(
            alert_id="alert-001",
            response_speed=ResponseSpeed.IMMEDIATE,
        )
        eng.record_response(
            alert_id="alert-002",
            response_speed=ResponseSpeed.SLOW,
        )
        results = eng.list_responses(response_speed=ResponseSpeed.IMMEDIATE)
        assert len(results) == 1

    def test_filter_by_responder(self):
        eng = _engine()
        eng.record_response(alert_id="alert-001", responder="alice")
        eng.record_response(alert_id="alert-002", responder="bob")
        results = eng.list_responses(responder="alice")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_response(alert_id=f"alert-{i}")
        assert len(eng.list_responses(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            metric_name="q1-response-metric",
            response_action=ResponseAction.RESOLVED,
            avg_response_time=8.5,
            total_responses=25,
            description="Quarterly response time metric",
        )
        assert m.metric_name == "q1-response-metric"
        assert m.response_action == ResponseAction.RESOLVED
        assert m.avg_response_time == 8.5
        assert m.total_responses == 25

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(metric_name=f"metric-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_response_times
# ---------------------------------------------------------------------------


class TestAnalyzeResponseTimes:
    def test_with_data(self):
        eng = _engine()
        eng.record_response(
            alert_id="alert-001",
            response_action=ResponseAction.ACKNOWLEDGED,
            response_time_minutes=10.0,
        )
        eng.record_response(
            alert_id="alert-002",
            response_action=ResponseAction.ACKNOWLEDGED,
            response_time_minutes=20.0,
        )
        result = eng.analyze_response_times()
        assert "acknowledged" in result
        assert result["acknowledged"]["count"] == 2
        assert result["acknowledged"]["avg_response_time_minutes"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_response_times() == {}


# ---------------------------------------------------------------------------
# identify_slow_responses
# ---------------------------------------------------------------------------


class TestIdentifySlowResponses:
    def test_detects_slow(self):
        eng = _engine(max_response_time_minutes=15.0)
        eng.record_response(
            alert_id="alert-001",
            response_time_minutes=30.0,
        )
        eng.record_response(
            alert_id="alert-002",
            response_time_minutes=5.0,
        )
        results = eng.identify_slow_responses()
        assert len(results) == 1
        assert results[0]["alert_id"] == "alert-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_responses() == []


# ---------------------------------------------------------------------------
# rank_by_response_speed
# ---------------------------------------------------------------------------


class TestRankByResponseSpeed:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_response(alert_id="a1", responder="alice", response_time_minutes=10.0)
        eng.record_response(alert_id="a2", responder="alice", response_time_minutes=5.0)
        eng.record_response(alert_id="a3", responder="bob", response_time_minutes=50.0)
        results = eng.rank_by_response_speed()
        assert len(results) == 2
        assert results[0]["responder"] == "alice"
        assert results[0]["total_response_time"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_response_speed() == []


# ---------------------------------------------------------------------------
# detect_response_patterns
# ---------------------------------------------------------------------------


class TestDetectResponsePatterns:
    def test_stable(self):
        eng = _engine()
        for t in [10.0, 10.0, 10.0, 10.0]:
            eng.record_response(alert_id="alert-001", response_time_minutes=t)
        result = eng.detect_response_patterns()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for t in [5.0, 5.0, 25.0, 25.0]:
            eng.record_response(alert_id="alert-001", response_time_minutes=t)
        result = eng.detect_response_patterns()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_response_patterns()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_response_time_minutes=15.0)
        eng.record_response(
            alert_id="alert-001",
            response_action=ResponseAction.ACKNOWLEDGED,
            response_speed=ResponseSpeed.SLOW,
            response_time_minutes=30.0,
            responder="alice",
        )
        report = eng.generate_report()
        assert isinstance(report, AlertResponseReport)
        assert report.total_records == 1
        assert report.avg_response_time_minutes == 30.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_response(alert_id="alert-001")
        eng.add_metric(metric_name="m1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["action_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_response(
            alert_id="alert-001",
            response_action=ResponseAction.RESOLVED,
            responder="alice",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_alerts"] == 1
        assert stats["unique_responders"] == 1
        assert "resolved" in stats["action_distribution"]
