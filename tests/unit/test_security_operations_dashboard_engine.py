"""Tests for SecurityOperationsDashboardEngine."""

from __future__ import annotations

from shieldops.security.security_operations_dashboard_engine import (
    AlertSeverity,
    AnalystTier,
    DashboardReport,
    MetricCategory,
    ResponseTimeRecord,
    SecurityOperationsDashboardEngine,
    SOCMetric,
)


def _engine(**kw) -> SecurityOperationsDashboardEngine:
    return SecurityOperationsDashboardEngine(**kw)


# --- Enum tests ---


class TestEnums:
    def test_severity_info(self):
        assert AlertSeverity.INFO == "info"

    def test_severity_low(self):
        assert AlertSeverity.LOW == "low"

    def test_severity_medium(self):
        assert AlertSeverity.MEDIUM == "medium"

    def test_severity_high(self):
        assert AlertSeverity.HIGH == "high"

    def test_severity_critical(self):
        assert AlertSeverity.CRITICAL == "critical"

    def test_tier_1(self):
        assert AnalystTier.TIER_1 == "tier_1"

    def test_tier_2(self):
        assert AnalystTier.TIER_2 == "tier_2"

    def test_tier_3(self):
        assert AnalystTier.TIER_3 == "tier_3"

    def test_tier_lead(self):
        assert AnalystTier.LEAD == "lead"

    def test_category_mttd(self):
        assert MetricCategory.MTTD == "mttd"

    def test_category_mttr(self):
        assert MetricCategory.MTTR == "mttr"

    def test_category_alert_volume(self):
        assert MetricCategory.ALERT_VOLUME == "alert_volume"

    def test_category_fp_rate(self):
        assert MetricCategory.FALSE_POSITIVE_RATE == "false_positive_rate"

    def test_category_escalation(self):
        assert MetricCategory.ESCALATION_RATE == "escalation_rate"


# --- Model tests ---


class TestModels:
    def test_metric_defaults(self):
        m = SOCMetric()
        assert m.id
        assert m.category == MetricCategory.MTTD
        assert m.value == 0.0

    def test_response_defaults(self):
        r = ResponseTimeRecord()
        assert r.id
        assert r.detection_time_ms == 0.0

    def test_report_defaults(self):
        r = DashboardReport()
        assert r.total_metrics == 0
        assert r.avg_mttd == 0.0


# --- compute_soc_metrics ---


class TestComputeMetrics:
    def test_basic(self):
        eng = _engine()
        m = eng.compute_soc_metrics(
            category=MetricCategory.MTTD,
            value=45000.0,
            severity=AlertSeverity.HIGH,
            analyst_id="a1",
            tier=AnalystTier.TIER_2,
            service="siem",
            team="soc",
        )
        assert m.category == MetricCategory.MTTD
        assert m.value == 45000.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.compute_soc_metrics(value=float(i))
        assert len(eng._metrics) == 3


# --- track_response_times ---


class TestTrackResponse:
    def test_basic(self):
        eng = _engine()
        r = eng.track_response_times(
            alert_id="alert-1",
            severity=AlertSeverity.CRITICAL,
            detection_time_ms=5000.0,
            response_time_ms=30000.0,
            resolution_time_ms=120000.0,
            analyst_id="a1",
        )
        assert r.alert_id == "alert-1"
        assert r.detection_time_ms == 5000.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.track_response_times(alert_id=f"a-{i}")
        assert len(eng._responses) == 3


# --- analyze_alert_volume ---


class TestAnalyzeAlertVolume:
    def test_with_data(self):
        eng = _engine()
        eng.track_response_times(alert_id="a1", severity=AlertSeverity.HIGH)
        eng.track_response_times(alert_id="a2", severity=AlertSeverity.HIGH)
        eng.track_response_times(alert_id="a3", severity=AlertSeverity.LOW)
        result = eng.analyze_alert_volume()
        assert result["total"] == 3
        assert result["by_severity"]["high"] == 2

    def test_empty(self):
        eng = _engine()
        result = eng.analyze_alert_volume()
        assert result["total"] == 0


# --- score_analyst_performance ---


class TestScoreAnalyst:
    def test_good_performance(self):
        eng = _engine(mttd_threshold_ms=60000.0, mttr_threshold_ms=300000.0)
        eng.track_response_times(
            alert_id="a1",
            analyst_id="analyst-1",
            detection_time_ms=10000.0,
            response_time_ms=50000.0,
        )
        result = eng.score_analyst_performance("analyst-1")
        assert result["score"] > 50.0
        assert result["alerts_handled"] == 1

    def test_no_data(self):
        eng = _engine()
        result = eng.score_analyst_performance("unknown")
        assert result["score"] == 0.0
        assert result["alerts_handled"] == 0

    def test_poor_performance(self):
        eng = _engine(mttd_threshold_ms=1000.0, mttr_threshold_ms=1000.0)
        eng.track_response_times(
            alert_id="a1",
            analyst_id="a1",
            detection_time_ms=5000.0,
            response_time_ms=5000.0,
        )
        result = eng.score_analyst_performance("a1")
        assert result["score"] == 0.0


# --- get_dashboard_data ---


class TestDashboardData:
    def test_with_data(self):
        eng = _engine(mttd_threshold_ms=60000.0, mttr_threshold_ms=300000.0)
        eng.track_response_times(
            alert_id="a1",
            detection_time_ms=10000.0,
            response_time_ms=50000.0,
        )
        eng.compute_soc_metrics(category=MetricCategory.MTTD, value=10000.0)
        data = eng.get_dashboard_data()
        assert data["avg_mttd"] == 10000.0
        assert data["total_alerts"] == 1
        assert data["sla_breaches"] == []

    def test_sla_breach(self):
        eng = _engine(mttd_threshold_ms=1000.0, mttr_threshold_ms=1000.0)
        eng.track_response_times(
            alert_id="a1",
            detection_time_ms=5000.0,
            response_time_ms=5000.0,
        )
        data = eng.get_dashboard_data()
        assert len(data["sla_breaches"]) == 2

    def test_empty(self):
        eng = _engine()
        data = eng.get_dashboard_data()
        assert data["avg_mttd"] == 0.0
        assert data["total_alerts"] == 0


# --- generate_report ---


class TestReport:
    def test_populated(self):
        eng = _engine(mttd_threshold_ms=1000.0)
        eng.track_response_times(
            alert_id="a1",
            detection_time_ms=5000.0,
            response_time_ms=5000.0,
        )
        eng.compute_soc_metrics(category=MetricCategory.MTTD)
        report = eng.generate_report()
        assert isinstance(report, DashboardReport)
        assert report.total_responses == 1
        assert report.total_metrics == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "healthy range" in report.recommendations[0]

    def test_sla_issues(self):
        eng = _engine(mttd_threshold_ms=100.0)
        eng.track_response_times(alert_id="a1", detection_time_ms=5000.0)
        report = eng.generate_report()
        assert any("MTTD" in i for i in report.top_issues)


# --- stats / clear ---


class TestStatsAndClear:
    def test_stats(self):
        eng = _engine()
        eng.compute_soc_metrics()
        eng.track_response_times(alert_id="a1", analyst_id="x")
        stats = eng.get_stats()
        assert stats["total_metrics"] == 1
        assert stats["total_responses"] == 1
        assert stats["unique_analysts"] == 1

    def test_clear(self):
        eng = _engine()
        eng.compute_soc_metrics()
        eng.track_response_times(alert_id="a1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._metrics) == 0
        assert len(eng._responses) == 0
