"""Tests for breach_notification_orchestrator — BreachNotificationOrchestrator."""

from __future__ import annotations

from shieldops.incidents.breach_notification_orchestrator import (
    BreachNotificationOrchestrator,
    BreachNotificationReport,
    BreachSeverity,
    NotificationAnalysis,
    NotificationChannel,
    NotificationDeadline,
    NotificationRecord,
)


def _engine(**kw) -> BreachNotificationOrchestrator:
    return BreachNotificationOrchestrator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_channel_email(self):
        assert NotificationChannel.EMAIL == "email"

    def test_channel_regulator(self):
        assert NotificationChannel.REGULATOR == "regulator"

    def test_channel_affected_users(self):
        assert NotificationChannel.AFFECTED_USERS == "affected_users"

    def test_channel_media(self):
        assert NotificationChannel.MEDIA == "media"

    def test_channel_internal(self):
        assert NotificationChannel.INTERNAL == "internal"

    def test_deadline_hours_24(self):
        assert NotificationDeadline.HOURS_24 == "hours_24"

    def test_deadline_hours_48(self):
        assert NotificationDeadline.HOURS_48 == "hours_48"

    def test_deadline_hours_72(self):
        assert NotificationDeadline.HOURS_72 == "hours_72"

    def test_deadline_days_30(self):
        assert NotificationDeadline.DAYS_30 == "days_30"

    def test_deadline_days_60(self):
        assert NotificationDeadline.DAYS_60 == "days_60"

    def test_severity_critical(self):
        assert BreachSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert BreachSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert BreachSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert BreachSeverity.LOW == "low"

    def test_severity_informational(self):
        assert BreachSeverity.INFORMATIONAL == "informational"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_notification_record_defaults(self):
        r = NotificationRecord()
        assert r.id
        assert r.breach_id == ""
        assert r.notification_channel == NotificationChannel.INTERNAL
        assert r.notification_deadline == NotificationDeadline.HOURS_72
        assert r.breach_severity == BreachSeverity.MEDIUM
        assert r.delivery_score == 0.0
        assert r.responder == ""
        assert r.business_unit == ""
        assert r.created_at > 0

    def test_notification_analysis_defaults(self):
        a = NotificationAnalysis()
        assert a.id
        assert a.breach_id == ""
        assert a.notification_channel == NotificationChannel.INTERNAL
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = BreachNotificationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_delivery_score == 0.0
        assert r.by_channel == {}
        assert r.by_deadline == {}
        assert r.by_severity == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_notification / get_notification
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_notification(
            breach_id="breach-001",
            notification_channel=NotificationChannel.REGULATOR,
            notification_deadline=NotificationDeadline.HOURS_72,
            breach_severity=BreachSeverity.CRITICAL,
            delivery_score=95.0,
            responder="dpo-team",
            business_unit="legal",
        )
        assert r.breach_id == "breach-001"
        assert r.notification_channel == NotificationChannel.REGULATOR
        assert r.delivery_score == 95.0
        assert r.responder == "dpo-team"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_notification(breach_id="breach-001", breach_severity=BreachSeverity.HIGH)
        result = eng.get_notification(r.id)
        assert result is not None
        assert result.breach_severity == BreachSeverity.HIGH

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_notification("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_notification(breach_id=f"breach-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_notifications
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_notification(breach_id="b-001")
        eng.record_notification(breach_id="b-002")
        assert len(eng.list_notifications()) == 2

    def test_filter_by_channel(self):
        eng = _engine()
        eng.record_notification(
            breach_id="b-001", notification_channel=NotificationChannel.REGULATOR
        )
        eng.record_notification(breach_id="b-002", notification_channel=NotificationChannel.MEDIA)
        results = eng.list_notifications(notification_channel=NotificationChannel.REGULATOR)
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_notification(breach_id="b-001", breach_severity=BreachSeverity.CRITICAL)
        eng.record_notification(breach_id="b-002", breach_severity=BreachSeverity.LOW)
        results = eng.list_notifications(breach_severity=BreachSeverity.CRITICAL)
        assert len(results) == 1

    def test_filter_by_unit(self):
        eng = _engine()
        eng.record_notification(breach_id="b-001", business_unit="legal")
        eng.record_notification(breach_id="b-002", business_unit="engineering")
        results = eng.list_notifications(business_unit="legal")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_notification(breach_id=f"b-{i}")
        assert len(eng.list_notifications(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            breach_id="breach-001",
            notification_channel=NotificationChannel.AFFECTED_USERS,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="notification delay",
        )
        assert a.breach_id == "breach-001"
        assert a.notification_channel == NotificationChannel.AFFECTED_USERS
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(breach_id=f"b-{i}")
        assert len(eng._analyses) == 2

    def test_stored_in_analyses(self):
        eng = _engine()
        eng.add_analysis(breach_id="breach-999", notification_channel=NotificationChannel.EMAIL)
        assert len(eng._analyses) == 1


# ---------------------------------------------------------------------------
# analyze_channel_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_notification(
            breach_id="b-001",
            notification_channel=NotificationChannel.REGULATOR,
            delivery_score=90.0,
        )
        eng.record_notification(
            breach_id="b-002",
            notification_channel=NotificationChannel.REGULATOR,
            delivery_score=70.0,
        )
        result = eng.analyze_channel_distribution()
        assert "regulator" in result
        assert result["regulator"]["count"] == 2
        assert result["regulator"]["avg_delivery_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_channel_distribution() == {}


# ---------------------------------------------------------------------------
# identify_notification_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_notification(breach_id="b-001", delivery_score=60.0)
        eng.record_notification(breach_id="b-002", delivery_score=90.0)
        results = eng.identify_notification_gaps()
        assert len(results) == 1
        assert results[0]["breach_id"] == "b-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_notification(breach_id="b-001", delivery_score=50.0)
        eng.record_notification(breach_id="b-002", delivery_score=30.0)
        results = eng.identify_notification_gaps()
        assert results[0]["delivery_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_delivery
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_notification(breach_id="b-001", business_unit="legal", delivery_score=90.0)
        eng.record_notification(breach_id="b-002", business_unit="engineering", delivery_score=50.0)
        results = eng.rank_by_delivery()
        assert results[0]["business_unit"] == "engineering"
        assert results[0]["avg_delivery_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_delivery() == []


# ---------------------------------------------------------------------------
# detect_notification_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(breach_id="b-001", analysis_score=50.0)
        result = eng.detect_notification_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(breach_id="b-001", analysis_score=20.0)
        eng.add_analysis(breach_id="b-002", analysis_score=20.0)
        eng.add_analysis(breach_id="b-003", analysis_score=80.0)
        eng.add_analysis(breach_id="b-004", analysis_score=80.0)
        result = eng.detect_notification_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_notification_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_notification(
            breach_id="breach-001",
            notification_channel=NotificationChannel.REGULATOR,
            notification_deadline=NotificationDeadline.HOURS_72,
            breach_severity=BreachSeverity.CRITICAL,
            delivery_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, BreachNotificationReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_notification(breach_id="b-001")
        eng.add_analysis(breach_id="b-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["channel_distribution"] == {}


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=3)
        for i in range(7):
            eng.add_analysis(breach_id=f"b-{i}")
        assert len(eng._analyses) == 3
