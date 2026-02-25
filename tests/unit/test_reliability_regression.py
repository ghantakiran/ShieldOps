"""Tests for shieldops.sla.reliability_regression — ReliabilityRegressionDetector."""

from __future__ import annotations

from shieldops.sla.reliability_regression import (
    CorrelationStrength,
    RegressionAnalysis,
    RegressionEvent,
    RegressionSeverity,
    RegressionType,
    ReliabilityRegressionDetector,
    ReliabilityRegressionReport,
)


def _engine(**kw) -> ReliabilityRegressionDetector:
    return ReliabilityRegressionDetector(**kw)


class TestEnums:
    def test_severity_critical(self):
        assert RegressionSeverity.CRITICAL == "critical"

    def test_severity_major(self):
        assert RegressionSeverity.MAJOR == "major"

    def test_severity_minor(self):
        assert RegressionSeverity.MINOR == "minor"

    def test_severity_cosmetic(self):
        assert RegressionSeverity.COSMETIC == "cosmetic"

    def test_severity_none(self):
        assert RegressionSeverity.NONE == "none"

    def test_type_error_rate(self):
        assert RegressionType.ERROR_RATE == "error_rate"

    def test_type_latency(self):
        assert RegressionType.LATENCY == "latency"

    def test_type_availability(self):
        assert RegressionType.AVAILABILITY == "availability"

    def test_type_throughput(self):
        assert RegressionType.THROUGHPUT == "throughput"

    def test_type_saturation(self):
        assert RegressionType.SATURATION == "saturation"

    def test_corr_strong(self):
        assert CorrelationStrength.STRONG == "strong"

    def test_corr_moderate(self):
        assert CorrelationStrength.MODERATE == "moderate"

    def test_corr_weak(self):
        assert CorrelationStrength.WEAK == "weak"

    def test_corr_coincidental(self):
        assert CorrelationStrength.COINCIDENTAL == "coincidental"

    def test_corr_unknown(self):
        assert CorrelationStrength.UNKNOWN == "unknown"


class TestModels:
    def test_regression_event_defaults(self):
        r = RegressionEvent()
        assert r.id
        assert r.service == ""
        assert r.change_id == ""
        assert r.regression_type == RegressionType.ERROR_RATE
        assert r.severity == RegressionSeverity.MINOR
        assert r.deviation_pct == 0.0
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = RegressionAnalysis()
        assert a.id
        assert a.total_regressions == 0

    def test_report_defaults(self):
        r = ReliabilityRegressionReport()
        assert r.total_regressions == 0
        assert r.recommendations == []


class TestRecordRegression:
    def test_basic(self):
        eng = _engine()
        r = eng.record_regression(
            service="svc-a",
            change_id="CHG-001",
            deviation_pct=30.0,
            correlation=CorrelationStrength.STRONG,
        )
        assert r.service == "svc-a"
        assert r.severity == RegressionSeverity.MAJOR

    def test_auto_severity_critical(self):
        eng = _engine(deviation_threshold_pct=10.0)
        r = eng.record_regression(service="svc-a", deviation_pct=60.0)
        assert r.severity == RegressionSeverity.CRITICAL

    def test_auto_severity_none(self):
        eng = _engine(deviation_threshold_pct=10.0)
        r = eng.record_regression(service="svc-a", deviation_pct=3.0)
        assert r.severity == RegressionSeverity.NONE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_regression(service=f"svc-{i}", deviation_pct=15.0)
        assert len(eng._records) == 3


class TestGetRegression:
    def test_found(self):
        eng = _engine()
        r = eng.record_regression(service="svc-a", deviation_pct=20.0)
        result = eng.get_regression(r.id)
        assert result is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_regression("nonexistent") is None


class TestListRegressions:
    def test_list_all(self):
        eng = _engine()
        eng.record_regression(service="svc-a", deviation_pct=20.0)
        eng.record_regression(service="svc-b", deviation_pct=30.0)
        assert len(eng.list_regressions()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_regression(service="svc-a", deviation_pct=20.0)
        eng.record_regression(service="svc-b", deviation_pct=30.0)
        results = eng.list_regressions(service="svc-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_regression(
            service="svc-a", regression_type=RegressionType.LATENCY, deviation_pct=20.0
        )
        eng.record_regression(
            service="svc-b", regression_type=RegressionType.ERROR_RATE, deviation_pct=30.0
        )
        results = eng.list_regressions(regression_type=RegressionType.LATENCY)
        assert len(results) == 1


class TestDetectRegressionsForChange:
    def test_finds(self):
        eng = _engine()
        eng.record_regression(service="svc-a", change_id="CHG-001", deviation_pct=20.0)
        eng.record_regression(service="svc-b", change_id="CHG-001", deviation_pct=30.0)
        results = eng.detect_regressions_for_change("CHG-001")
        assert len(results) == 2

    def test_empty(self):
        eng = _engine()
        assert eng.detect_regressions_for_change("CHG-999") == []


class TestAnalyzeServiceRegressions:
    def test_with_data(self):
        eng = _engine()
        eng.record_regression(service="svc-a", deviation_pct=20.0)
        eng.record_regression(service="svc-a", deviation_pct=30.0)
        result = eng.analyze_service_regressions("svc-a")
        assert result["total_regressions"] == 2
        assert result["avg_deviation_pct"] == 25.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_service_regressions("unknown")
        assert result["total_regressions"] == 0


class TestIdentifyRegressionProneServices:
    def test_ranked(self):
        eng = _engine()
        eng.record_regression(service="svc-a", deviation_pct=20.0)
        eng.record_regression(service="svc-a", deviation_pct=30.0)
        eng.record_regression(service="svc-b", deviation_pct=10.0)
        results = eng.identify_regression_prone_services()
        assert results[0]["service"] == "svc-a"
        assert results[0]["regression_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_regression_prone_services() == []


class TestCorrelateWithChanges:
    def test_with_data(self):
        eng = _engine()
        eng.record_regression(service="svc-a", change_id="CHG-001", deviation_pct=20.0)
        results = eng.correlate_with_changes()
        assert len(results) == 1
        assert results[0]["change_id"] == "CHG-001"

    def test_empty(self):
        eng = _engine()
        assert eng.correlate_with_changes() == []


class TestCalculateRegressionRate:
    def test_with_data(self):
        eng = _engine(deviation_threshold_pct=10.0)
        eng.record_regression(service="svc-a", deviation_pct=60.0)
        eng.record_regression(service="svc-b", deviation_pct=5.0)
        result = eng.calculate_regression_rate()
        assert result["total"] == 2
        assert result["critical_count"] == 1

    def test_empty(self):
        eng = _engine()
        result = eng.calculate_regression_rate()
        assert result["total"] == 0


class TestGenerateReportRR:
    def test_populated(self):
        eng = _engine(deviation_threshold_pct=10.0)
        eng.record_regression(service="svc-a", deviation_pct=60.0)
        report = eng.generate_report()
        assert isinstance(report, ReliabilityRegressionReport)
        assert report.total_regressions == 1
        assert report.critical_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "No significant reliability regressions detected" in report.recommendations


class TestClearDataRR:
    def test_clears(self):
        eng = _engine()
        eng.record_regression(service="svc-a", deviation_pct=20.0)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0


class TestGetStatsRR:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_regressions"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_regression(service="svc-a", change_id="CHG-001", deviation_pct=20.0)
        stats = eng.get_stats()
        assert stats["total_regressions"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_changes"] == 1
