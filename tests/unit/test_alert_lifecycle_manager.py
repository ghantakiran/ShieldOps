"""Tests for shieldops.security.alert_lifecycle_manager — AlertLifecycleManager."""

from __future__ import annotations

from shieldops.security.alert_lifecycle_manager import (
    AlertLifecycleAnalysis,
    AlertLifecycleManager,
    AlertLifecycleRecord,
    AlertLifecycleReport,
    AlertPhase,
    AlertPriority,
    AlertSource,
)


def _engine(**kw) -> AlertLifecycleManager:
    return AlertLifecycleManager(**kw)


class TestEnums:
    def test_alertphase_val1(self):
        assert AlertPhase.CREATED == "created"

    def test_alertphase_val2(self):
        assert AlertPhase.TRIAGED == "triaged"

    def test_alertphase_val3(self):
        assert AlertPhase.INVESTIGATED == "investigated"

    def test_alertphase_val4(self):
        assert AlertPhase.RESOLVED == "resolved"

    def test_alertphase_val5(self):
        assert AlertPhase.CLOSED == "closed"

    def test_alertpriority_val1(self):
        assert AlertPriority.CRITICAL == "critical"

    def test_alertpriority_val2(self):
        assert AlertPriority.HIGH == "high"

    def test_alertpriority_val3(self):
        assert AlertPriority.MEDIUM == "medium"

    def test_alertpriority_val4(self):
        assert AlertPriority.LOW == "low"

    def test_alertpriority_val5(self):
        assert AlertPriority.INFORMATIONAL == "informational"

    def test_alertsource_val1(self):
        assert AlertSource.SIEM == "siem"

    def test_alertsource_val2(self):
        assert AlertSource.EDR == "edr"

    def test_alertsource_val3(self):
        assert AlertSource.NDR == "ndr"

    def test_alertsource_val4(self):
        assert AlertSource.CLOUD == "cloud"

    def test_alertsource_val5(self):
        assert AlertSource.CUSTOM == "custom"


class TestModels:
    def test_record_defaults(self):
        r = AlertLifecycleRecord()
        assert r.id
        assert r.alert_name == ""

    def test_analysis_defaults(self):
        a = AlertLifecycleAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = AlertLifecycleReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_alert(
            alert_name="test",
            alert_phase=AlertPhase.TRIAGED,
            lifecycle_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.alert_name == "test"
        assert r.lifecycle_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_alert(alert_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_alert(alert_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_alert(alert_name="a")
        eng.record_alert(alert_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_alert(alert_name="a", alert_phase=AlertPhase.CREATED)
        eng.record_alert(alert_name="b", alert_phase=AlertPhase.TRIAGED)
        assert len(eng.list_records(alert_phase=AlertPhase.CREATED)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_alert(alert_name="a", alert_priority=AlertPriority.CRITICAL)
        eng.record_alert(alert_name="b", alert_priority=AlertPriority.HIGH)
        assert len(eng.list_records(alert_priority=AlertPriority.CRITICAL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_alert(alert_name="a", team="sec")
        eng.record_alert(alert_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_alert(alert_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            alert_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(alert_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_alert(alert_name="a", alert_phase=AlertPhase.CREATED, lifecycle_score=90.0)
        eng.record_alert(alert_name="b", alert_phase=AlertPhase.CREATED, lifecycle_score=70.0)
        result = eng.analyze_distribution()
        assert AlertPhase.CREATED.value in result
        assert result[AlertPhase.CREATED.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_alert(alert_name="a", lifecycle_score=60.0)
        eng.record_alert(alert_name="b", lifecycle_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_alert(alert_name="a", lifecycle_score=50.0)
        eng.record_alert(alert_name="b", lifecycle_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["lifecycle_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_alert(alert_name="a", service="auth", lifecycle_score=90.0)
        eng.record_alert(alert_name="b", service="api", lifecycle_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(alert_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(alert_name="a", analysis_score=20.0)
        eng.add_analysis(alert_name="b", analysis_score=20.0)
        eng.add_analysis(alert_name="c", analysis_score=80.0)
        eng.add_analysis(alert_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_alert(alert_name="test", lifecycle_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_alert(alert_name="test")
        eng.add_analysis(alert_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_alert(alert_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
