"""Tests for shieldops.changes.change_window_analyzer — ChangeWindowAnalyzer."""

from __future__ import annotations

from shieldops.changes.change_window_analyzer import (
    ChangeWindowAnalyzer,
    ChangeWindowReport,
    SchedulingEfficiency,
    WindowCompliance,
    WindowMetric,
    WindowRecord,
    WindowType,
)


def _engine(**kw) -> ChangeWindowAnalyzer:
    return ChangeWindowAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_compliance_within_window(self):
        assert WindowCompliance.WITHIN_WINDOW == "within_window"

    def test_compliance_early(self):
        assert WindowCompliance.EARLY == "early"

    def test_compliance_late(self):
        assert WindowCompliance.LATE == "late"

    def test_compliance_emergency(self):
        assert WindowCompliance.EMERGENCY == "emergency"

    def test_compliance_unauthorized(self):
        assert WindowCompliance.UNAUTHORIZED == "unauthorized"

    def test_type_standard(self):
        assert WindowType.STANDARD == "standard"

    def test_type_maintenance(self):
        assert WindowType.MAINTENANCE == "maintenance"

    def test_type_emergency(self):
        assert WindowType.EMERGENCY == "emergency"

    def test_type_freeze(self):
        assert WindowType.FREEZE == "freeze"

    def test_type_custom(self):
        assert WindowType.CUSTOM == "custom"

    def test_efficiency_optimal(self):
        assert SchedulingEfficiency.OPTIMAL == "optimal"

    def test_efficiency_good(self):
        assert SchedulingEfficiency.GOOD == "good"

    def test_efficiency_fair(self):
        assert SchedulingEfficiency.FAIR == "fair"

    def test_efficiency_poor(self):
        assert SchedulingEfficiency.POOR == "poor"

    def test_efficiency_wasted(self):
        assert SchedulingEfficiency.WASTED == "wasted"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_window_record_defaults(self):
        r = WindowRecord()
        assert r.id
        assert r.window_id == ""
        assert r.window_compliance == WindowCompliance.WITHIN_WINDOW
        assert r.window_type == WindowType.STANDARD
        assert r.scheduling_efficiency == SchedulingEfficiency.GOOD
        assert r.utilization_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_window_metric_defaults(self):
        m = WindowMetric()
        assert m.id
        assert m.window_id == ""
        assert m.window_compliance == WindowCompliance.WITHIN_WINDOW
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_window_report_defaults(self):
        r = ChangeWindowReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.non_compliant_count == 0
        assert r.avg_utilization_pct == 0.0
        assert r.by_compliance == {}
        assert r.by_type == {}
        assert r.by_efficiency == {}
        assert r.top_non_compliant == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_window
# ---------------------------------------------------------------------------


class TestRecordWindow:
    def test_basic(self):
        eng = _engine()
        r = eng.record_window(
            window_id="WIN-001",
            window_compliance=WindowCompliance.WITHIN_WINDOW,
            window_type=WindowType.MAINTENANCE,
            scheduling_efficiency=SchedulingEfficiency.OPTIMAL,
            utilization_pct=92.0,
            service="api-gateway",
            team="sre",
        )
        assert r.window_id == "WIN-001"
        assert r.window_compliance == WindowCompliance.WITHIN_WINDOW
        assert r.window_type == WindowType.MAINTENANCE
        assert r.scheduling_efficiency == SchedulingEfficiency.OPTIMAL
        assert r.utilization_pct == 92.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_window(window_id=f"WIN-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_window
# ---------------------------------------------------------------------------


class TestGetWindow:
    def test_found(self):
        eng = _engine()
        r = eng.record_window(
            window_id="WIN-001",
            window_compliance=WindowCompliance.LATE,
        )
        result = eng.get_window(r.id)
        assert result is not None
        assert result.window_compliance == WindowCompliance.LATE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_window("nonexistent") is None


# ---------------------------------------------------------------------------
# list_windows
# ---------------------------------------------------------------------------


class TestListWindows:
    def test_list_all(self):
        eng = _engine()
        eng.record_window(window_id="WIN-001")
        eng.record_window(window_id="WIN-002")
        assert len(eng.list_windows()) == 2

    def test_filter_by_compliance(self):
        eng = _engine()
        eng.record_window(
            window_id="WIN-001",
            window_compliance=WindowCompliance.WITHIN_WINDOW,
        )
        eng.record_window(
            window_id="WIN-002",
            window_compliance=WindowCompliance.LATE,
        )
        results = eng.list_windows(compliance=WindowCompliance.WITHIN_WINDOW)
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_window(
            window_id="WIN-001",
            window_type=WindowType.STANDARD,
        )
        eng.record_window(
            window_id="WIN-002",
            window_type=WindowType.EMERGENCY,
        )
        results = eng.list_windows(window_type=WindowType.STANDARD)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_window(window_id="WIN-001", team="sre")
        eng.record_window(window_id="WIN-002", team="platform")
        results = eng.list_windows(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_window(window_id=f"WIN-{i}")
        assert len(eng.list_windows(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            window_id="WIN-001",
            window_compliance=WindowCompliance.WITHIN_WINDOW,
            metric_score=88.0,
            threshold=85.0,
            breached=True,
            description="Utilization check",
        )
        assert m.window_id == "WIN-001"
        assert m.window_compliance == WindowCompliance.WITHIN_WINDOW
        assert m.metric_score == 88.0
        assert m.threshold == 85.0
        assert m.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(window_id=f"WIN-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_window_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeWindowDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_window(
            window_id="WIN-001",
            window_compliance=WindowCompliance.WITHIN_WINDOW,
            utilization_pct=80.0,
        )
        eng.record_window(
            window_id="WIN-002",
            window_compliance=WindowCompliance.WITHIN_WINDOW,
            utilization_pct=90.0,
        )
        result = eng.analyze_window_distribution()
        assert "within_window" in result
        assert result["within_window"]["count"] == 2
        assert result["within_window"]["avg_utilization_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_window_distribution() == {}


# ---------------------------------------------------------------------------
# identify_non_compliant
# ---------------------------------------------------------------------------


class TestIdentifyNonCompliant:
    def test_detects_late(self):
        eng = _engine()
        eng.record_window(
            window_id="WIN-001",
            window_compliance=WindowCompliance.LATE,
        )
        eng.record_window(
            window_id="WIN-002",
            window_compliance=WindowCompliance.WITHIN_WINDOW,
        )
        results = eng.identify_non_compliant()
        assert len(results) == 1
        assert results[0]["window_id"] == "WIN-001"

    def test_detects_emergency(self):
        eng = _engine()
        eng.record_window(
            window_id="WIN-001",
            window_compliance=WindowCompliance.EMERGENCY,
        )
        results = eng.identify_non_compliant()
        assert len(results) == 1

    def test_detects_unauthorized(self):
        eng = _engine()
        eng.record_window(
            window_id="WIN-001",
            window_compliance=WindowCompliance.UNAUTHORIZED,
        )
        results = eng.identify_non_compliant()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_non_compliant() == []


# ---------------------------------------------------------------------------
# rank_by_utilization
# ---------------------------------------------------------------------------


class TestRankByUtilization:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_window(window_id="WIN-001", utilization_pct=95.0, service="svc-a")
        eng.record_window(window_id="WIN-002", utilization_pct=40.0, service="svc-b")
        results = eng.rank_by_utilization()
        assert len(results) == 2
        assert results[0]["service"] == "svc-b"
        assert results[0]["avg_utilization_pct"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_utilization() == []


# ---------------------------------------------------------------------------
# detect_window_trends
# ---------------------------------------------------------------------------


class TestDetectWindowTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_metric(window_id="WIN-001", metric_score=70.0)
        result = eng.detect_window_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_metric(window_id="WIN-001", metric_score=50.0)
        eng.add_metric(window_id="WIN-002", metric_score=50.0)
        eng.add_metric(window_id="WIN-003", metric_score=80.0)
        eng.add_metric(window_id="WIN-004", metric_score=80.0)
        result = eng.detect_window_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_window_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_window(
            window_id="WIN-001",
            window_compliance=WindowCompliance.UNAUTHORIZED,
            utilization_pct=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ChangeWindowReport)
        assert report.total_records == 1
        assert report.non_compliant_count == 1
        assert len(report.top_non_compliant) == 1
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
        eng.record_window(window_id="WIN-001")
        eng.add_metric(window_id="WIN-001")
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
        assert stats["compliance_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_window(
            window_id="WIN-001",
            window_compliance=WindowCompliance.WITHIN_WINDOW,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "within_window" in stats["compliance_distribution"]
