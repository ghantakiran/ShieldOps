"""Tests for shieldops.sla.slo_window_analyzer — SLOWindowAnalyzer."""

from __future__ import annotations

from shieldops.sla.slo_window_analyzer import (
    ComplianceStatus,
    SLOWindowAnalyzer,
    SLOWindowReport,
    WindowDuration,
    WindowEvaluation,
    WindowRecord,
    WindowStrategy,
)


def _engine(**kw) -> SLOWindowAnalyzer:
    return SLOWindowAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_duration_hourly(self):
        assert WindowDuration.HOURLY == "hourly"

    def test_duration_daily(self):
        assert WindowDuration.DAILY == "daily"

    def test_duration_weekly(self):
        assert WindowDuration.WEEKLY == "weekly"

    def test_duration_monthly(self):
        assert WindowDuration.MONTHLY == "monthly"

    def test_duration_quarterly(self):
        assert WindowDuration.QUARTERLY == "quarterly"

    def test_status_compliant(self):
        assert ComplianceStatus.COMPLIANT == "compliant"

    def test_status_at_risk(self):
        assert ComplianceStatus.AT_RISK == "at_risk"

    def test_status_breaching(self):
        assert ComplianceStatus.BREACHING == "breaching"

    def test_status_breached(self):
        assert ComplianceStatus.BREACHED == "breached"

    def test_status_unknown(self):
        assert ComplianceStatus.UNKNOWN == "unknown"

    def test_strategy_rolling(self):
        assert WindowStrategy.ROLLING == "rolling"

    def test_strategy_calendar(self):
        assert WindowStrategy.CALENDAR == "calendar"

    def test_strategy_sliding(self):
        assert WindowStrategy.SLIDING == "sliding"

    def test_strategy_fixed(self):
        assert WindowStrategy.FIXED == "fixed"

    def test_strategy_adaptive(self):
        assert WindowStrategy.ADAPTIVE == "adaptive"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_window_record_defaults(self):
        r = WindowRecord()
        assert r.id
        assert r.slo_id == ""
        assert r.window_duration == WindowDuration.MONTHLY
        assert r.compliance_status == ComplianceStatus.UNKNOWN
        assert r.window_strategy == WindowStrategy.ROLLING
        assert r.compliance_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_window_evaluation_defaults(self):
        m = WindowEvaluation()
        assert m.id
        assert m.slo_id == ""
        assert m.window_duration == WindowDuration.MONTHLY
        assert m.eval_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_slo_window_report_defaults(self):
        r = SLOWindowReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_evaluations == 0
        assert r.breaching_count == 0
        assert r.avg_compliance_pct == 0.0
        assert r.by_duration == {}
        assert r.by_status == {}
        assert r.by_strategy == {}
        assert r.top_breaching == []
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
            slo_id="SLO-001",
            window_duration=WindowDuration.WEEKLY,
            compliance_status=ComplianceStatus.BREACHING,
            window_strategy=WindowStrategy.CALENDAR,
            compliance_pct=92.5,
            service="api-gateway",
            team="sre",
        )
        assert r.slo_id == "SLO-001"
        assert r.window_duration == WindowDuration.WEEKLY
        assert r.compliance_status == ComplianceStatus.BREACHING
        assert r.window_strategy == WindowStrategy.CALENDAR
        assert r.compliance_pct == 92.5
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_window(slo_id=f"SLO-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_window
# ---------------------------------------------------------------------------


class TestGetWindow:
    def test_found(self):
        eng = _engine()
        r = eng.record_window(
            slo_id="SLO-001",
            compliance_status=ComplianceStatus.BREACHING,
        )
        result = eng.get_window(r.id)
        assert result is not None
        assert result.compliance_status == ComplianceStatus.BREACHING

    def test_not_found(self):
        eng = _engine()
        assert eng.get_window("nonexistent") is None


# ---------------------------------------------------------------------------
# list_windows
# ---------------------------------------------------------------------------


class TestListWindows:
    def test_list_all(self):
        eng = _engine()
        eng.record_window(slo_id="SLO-001")
        eng.record_window(slo_id="SLO-002")
        assert len(eng.list_windows()) == 2

    def test_filter_by_duration(self):
        eng = _engine()
        eng.record_window(
            slo_id="SLO-001",
            window_duration=WindowDuration.WEEKLY,
        )
        eng.record_window(
            slo_id="SLO-002",
            window_duration=WindowDuration.MONTHLY,
        )
        results = eng.list_windows(duration=WindowDuration.WEEKLY)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_window(
            slo_id="SLO-001",
            compliance_status=ComplianceStatus.COMPLIANT,
        )
        eng.record_window(
            slo_id="SLO-002",
            compliance_status=ComplianceStatus.BREACHING,
        )
        results = eng.list_windows(status=ComplianceStatus.BREACHING)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_window(slo_id="SLO-001", service="api-gateway")
        eng.record_window(slo_id="SLO-002", service="auth-svc")
        results = eng.list_windows(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_window(slo_id="SLO-001", team="sre")
        eng.record_window(slo_id="SLO-002", team="platform")
        results = eng.list_windows(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_window(slo_id=f"SLO-{i}")
        assert len(eng.list_windows(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_evaluation
# ---------------------------------------------------------------------------


class TestAddEvaluation:
    def test_basic(self):
        eng = _engine()
        m = eng.add_evaluation(
            slo_id="SLO-001",
            window_duration=WindowDuration.WEEKLY,
            eval_score=85.0,
            threshold=90.0,
            breached=True,
            description="SLO compliance dropped below threshold",
        )
        assert m.slo_id == "SLO-001"
        assert m.window_duration == WindowDuration.WEEKLY
        assert m.eval_score == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "SLO compliance dropped below threshold"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_evaluation(slo_id=f"SLO-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_window_compliance
# ---------------------------------------------------------------------------


class TestAnalyzeWindowCompliance:
    def test_with_data(self):
        eng = _engine()
        eng.record_window(
            slo_id="SLO-001",
            window_duration=WindowDuration.MONTHLY,
            compliance_pct=99.0,
        )
        eng.record_window(
            slo_id="SLO-002",
            window_duration=WindowDuration.MONTHLY,
            compliance_pct=97.0,
        )
        result = eng.analyze_window_compliance()
        assert "monthly" in result
        assert result["monthly"]["count"] == 2
        assert result["monthly"]["avg_compliance_pct"] == 98.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_window_compliance() == {}


# ---------------------------------------------------------------------------
# identify_breaching_windows
# ---------------------------------------------------------------------------


class TestIdentifyBreachingWindows:
    def test_detects(self):
        eng = _engine()
        eng.record_window(
            slo_id="SLO-001",
            compliance_status=ComplianceStatus.BREACHING,
        )
        eng.record_window(
            slo_id="SLO-002",
            compliance_status=ComplianceStatus.COMPLIANT,
        )
        results = eng.identify_breaching_windows()
        assert len(results) == 1
        assert results[0]["slo_id"] == "SLO-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_breaching_windows() == []


# ---------------------------------------------------------------------------
# rank_by_compliance
# ---------------------------------------------------------------------------


class TestRankByCompliance:
    def test_ranked(self):
        eng = _engine()
        eng.record_window(
            slo_id="SLO-001",
            service="api-gateway",
            compliance_pct=99.0,
        )
        eng.record_window(
            slo_id="SLO-002",
            service="auth-svc",
            compliance_pct=92.0,
        )
        eng.record_window(
            slo_id="SLO-003",
            service="api-gateway",
            compliance_pct=97.0,
        )
        results = eng.rank_by_compliance()
        assert len(results) == 2
        # ascending: auth-svc (92.0) first, api-gateway (98.0) second
        assert results[0]["service"] == "auth-svc"
        assert results[0]["avg_compliance_pct"] == 92.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance() == []


# ---------------------------------------------------------------------------
# detect_compliance_trends
# ---------------------------------------------------------------------------


class TestDetectComplianceTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.add_evaluation(slo_id="SLO-1", eval_score=val)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_evaluation(slo_id="SLO-1", eval_score=val)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_degrading(self):
        eng = _engine()
        for val in [20.0, 20.0, 5.0, 5.0]:
            eng.add_evaluation(slo_id="SLO-1", eval_score=val)
        result = eng.detect_compliance_trends()
        assert result["trend"] == "degrading"
        assert result["delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_compliance_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_window(
            slo_id="SLO-001",
            window_duration=WindowDuration.WEEKLY,
            compliance_status=ComplianceStatus.BREACHING,
            window_strategy=WindowStrategy.CALENDAR,
            compliance_pct=92.5,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, SLOWindowReport)
        assert report.total_records == 1
        assert report.breaching_count == 1
        assert len(report.top_breaching) >= 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_window(slo_id="SLO-001")
        eng.add_evaluation(slo_id="SLO-001")
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
        assert stats["duration_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_window(
            slo_id="SLO-001",
            window_duration=WindowDuration.MONTHLY,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "monthly" in stats["duration_distribution"]
