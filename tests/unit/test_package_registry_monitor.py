"""Tests for shieldops.security.package_registry_monitor — PackageRegistryMonitor."""

from __future__ import annotations

from shieldops.security.package_registry_monitor import (
    AlertLevel,
    MonitorScope,
    PackageRegistryMonitor,
    PackageRegistryReport,
    RegistryEvent,
    RegistryMonitorAnalysis,
    RegistryMonitorRecord,
)


def _engine(**kw) -> PackageRegistryMonitor:
    return PackageRegistryMonitor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_event_publish(self):
        assert RegistryEvent.PUBLISH == "publish"

    def test_event_unpublish(self):
        assert RegistryEvent.UNPUBLISH == "unpublish"

    def test_event_deprecate(self):
        assert RegistryEvent.DEPRECATE == "deprecate"

    def test_event_security_advisory(self):
        assert RegistryEvent.SECURITY_ADVISORY == "security_advisory"

    def test_event_ownership_change(self):
        assert RegistryEvent.OWNERSHIP_CHANGE == "ownership_change"

    def test_scope_direct(self):
        assert MonitorScope.DIRECT == "direct"

    def test_scope_transitive(self):
        assert MonitorScope.TRANSITIVE == "transitive"

    def test_scope_all(self):
        assert MonitorScope.ALL == "all"

    def test_scope_critical(self):
        assert MonitorScope.CRITICAL == "critical"

    def test_scope_custom(self):
        assert MonitorScope.CUSTOM == "custom"

    def test_alert_critical(self):
        assert AlertLevel.CRITICAL == "critical"

    def test_alert_high(self):
        assert AlertLevel.HIGH == "high"

    def test_alert_medium(self):
        assert AlertLevel.MEDIUM == "medium"

    def test_alert_low(self):
        assert AlertLevel.LOW == "low"

    def test_alert_info(self):
        assert AlertLevel.INFO == "info"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_registry_monitor_record_defaults(self):
        r = RegistryMonitorRecord()
        assert r.id
        assert r.package_name == ""
        assert r.registry_event == RegistryEvent.PUBLISH
        assert r.monitor_scope == MonitorScope.ALL
        assert r.alert_level == AlertLevel.INFO
        assert r.monitor_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_registry_monitor_analysis_defaults(self):
        c = RegistryMonitorAnalysis()
        assert c.id
        assert c.package_name == ""
        assert c.registry_event == RegistryEvent.PUBLISH
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_package_registry_report_defaults(self):
        r = PackageRegistryReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_monitor_score == 0.0
        assert r.by_event == {}
        assert r.by_scope == {}
        assert r.by_alert_level == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_event / get / list
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_event(
            package_name="express",
            registry_event=RegistryEvent.SECURITY_ADVISORY,
            monitor_scope=MonitorScope.DIRECT,
            alert_level=AlertLevel.CRITICAL,
            monitor_score=15.0,
            service="npm-watch",
            team="security",
        )
        assert r.package_name == "express"
        assert r.registry_event == RegistryEvent.SECURITY_ADVISORY
        assert r.monitor_scope == MonitorScope.DIRECT
        assert r.alert_level == AlertLevel.CRITICAL
        assert r.monitor_score == 15.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_event(package_name="lodash", monitor_score=80.0)
        result = eng.get_event(r.id)
        assert result is not None
        assert result.monitor_score == 80.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_event("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_event(package_name=f"pkg-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_event(package_name="a")
        eng.record_event(package_name="b")
        assert len(eng.list_events()) == 2

    def test_filter_by_registry_event(self):
        eng = _engine()
        eng.record_event(package_name="a", registry_event=RegistryEvent.PUBLISH)
        eng.record_event(package_name="b", registry_event=RegistryEvent.DEPRECATE)
        results = eng.list_events(registry_event=RegistryEvent.PUBLISH)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_event(package_name="a", team="security")
        eng.record_event(package_name="b", team="platform")
        results = eng.list_events(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_event(package_name=f"pkg-{i}")
        assert len(eng.list_events(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            package_name="express",
            registry_event=RegistryEvent.OWNERSHIP_CHANGE,
            analysis_score=20.0,
            threshold=50.0,
            breached=True,
            description="suspicious ownership change",
        )
        assert a.package_name == "express"
        assert a.registry_event == RegistryEvent.OWNERSHIP_CHANGE
        assert a.analysis_score == 20.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(package_name=f"pkg-{i}")
        assert len(eng._analyses) == 2

    def test_filter_by_alert_level(self):
        eng = _engine()
        eng.record_event(package_name="a", alert_level=AlertLevel.CRITICAL)
        eng.record_event(package_name="b", alert_level=AlertLevel.INFO)
        results = eng.list_events(alert_level=AlertLevel.CRITICAL)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# analyze_event_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_event(package_name="a", registry_event=RegistryEvent.PUBLISH, monitor_score=90.0)
        eng.record_event(package_name="b", registry_event=RegistryEvent.PUBLISH, monitor_score=70.0)
        result = eng.analyze_event_distribution()
        assert "publish" in result
        assert result["publish"]["count"] == 2
        assert result["publish"]["avg_monitor_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_event_distribution() == {}


# ---------------------------------------------------------------------------
# identify_monitor_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(monitor_gap_threshold=60.0)
        eng.record_event(package_name="a", monitor_score=40.0)
        eng.record_event(package_name="b", monitor_score=80.0)
        results = eng.identify_monitor_gaps()
        assert len(results) == 1
        assert results[0]["package_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(monitor_gap_threshold=80.0)
        eng.record_event(package_name="a", monitor_score=50.0)
        eng.record_event(package_name="b", monitor_score=20.0)
        results = eng.identify_monitor_gaps()
        assert len(results) == 2
        assert results[0]["monitor_score"] == 20.0


# ---------------------------------------------------------------------------
# rank_by_monitor_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_event(package_name="a", service="npm-svc", monitor_score=90.0)
        eng.record_event(package_name="b", service="pypi-svc", monitor_score=30.0)
        results = eng.rank_by_monitor_score()
        assert len(results) == 2
        assert results[0]["service"] == "pypi-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_monitor_score() == []


# ---------------------------------------------------------------------------
# detect_monitor_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(package_name="pkg", analysis_score=50.0)
        result = eng.detect_monitor_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(package_name="pkg", analysis_score=20.0)
        eng.add_analysis(package_name="pkg", analysis_score=20.0)
        eng.add_analysis(package_name="pkg", analysis_score=80.0)
        eng.add_analysis(package_name="pkg", analysis_score=80.0)
        result = eng.detect_monitor_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_monitor_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(monitor_gap_threshold=60.0)
        eng.record_event(
            package_name="express",
            registry_event=RegistryEvent.SECURITY_ADVISORY,
            alert_level=AlertLevel.CRITICAL,
            monitor_score=20.0,
        )
        report = eng.generate_report()
        assert isinstance(report, PackageRegistryReport)
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
        eng.record_event(package_name="pkg")
        eng.add_analysis(package_name="pkg")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats(self):
        eng = _engine()
        eng.record_event(
            package_name="express",
            registry_event=RegistryEvent.PUBLISH,
            service="npm-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "publish" in stats["event_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.record_event(package_name=f"pkg-{i}")
        assert len(eng._records) == 2
        assert eng._records[-1].package_name == "pkg-4"
