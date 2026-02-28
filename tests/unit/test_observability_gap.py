"""Tests for shieldops.observability.observability_gap — ObservabilityGapDetector."""

from __future__ import annotations

from shieldops.observability.observability_gap import (
    CoverageAssessment,
    CoverageLevel,
    GapRecord,
    GapSeverity,
    GapType,
    ObservabilityGapDetector,
    ObservabilityGapReport,
)


def _engine(**kw) -> ObservabilityGapDetector:
    return ObservabilityGapDetector(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # GapType (5)
    def test_gap_type_missing_metrics(self):
        assert GapType.MISSING_METRICS == "missing_metrics"

    def test_gap_type_missing_traces(self):
        assert GapType.MISSING_TRACES == "missing_traces"

    def test_gap_type_missing_logs(self):
        assert GapType.MISSING_LOGS == "missing_logs"

    def test_gap_type_missing_alerts(self):
        assert GapType.MISSING_ALERTS == "missing_alerts"

    def test_gap_type_missing_dashboards(self):
        assert GapType.MISSING_DASHBOARDS == "missing_dashboards"

    # GapSeverity (5)
    def test_severity_critical(self):
        assert GapSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert GapSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert GapSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert GapSeverity.LOW == "low"

    def test_severity_informational(self):
        assert GapSeverity.INFORMATIONAL == "informational"

    # CoverageLevel (5)
    def test_coverage_full(self):
        assert CoverageLevel.FULL == "full"

    def test_coverage_high(self):
        assert CoverageLevel.HIGH == "high"

    def test_coverage_partial(self):
        assert CoverageLevel.PARTIAL == "partial"

    def test_coverage_minimal(self):
        assert CoverageLevel.MINIMAL == "minimal"

    def test_coverage_none(self):
        assert CoverageLevel.NONE == "none"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_gap_record_defaults(self):
        r = GapRecord()
        assert r.id
        assert r.service_name == ""
        assert r.gap_type == GapType.MISSING_METRICS
        assert r.severity == GapSeverity.MODERATE
        assert r.coverage == CoverageLevel.PARTIAL
        assert r.coverage_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_coverage_assessment_defaults(self):
        r = CoverageAssessment()
        assert r.id
        assert r.assessment_name == ""
        assert r.gap_type == GapType.MISSING_METRICS
        assert r.severity == GapSeverity.MODERATE
        assert r.target_coverage_pct == 80.0
        assert r.review_interval_days == 30
        assert r.created_at > 0

    def test_observability_gap_report_defaults(self):
        r = ObservabilityGapReport()
        assert r.total_gaps == 0
        assert r.total_assessments == 0
        assert r.coverage_rate_pct == 0.0
        assert r.by_gap_type == {}
        assert r.by_severity == {}
        assert r.critical_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_gap
# -------------------------------------------------------------------


class TestRecordGap:
    def test_basic(self):
        eng = _engine()
        r = eng.record_gap("api-gateway", gap_type=GapType.MISSING_METRICS)
        assert r.service_name == "api-gateway"
        assert r.gap_type == GapType.MISSING_METRICS

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_gap(
            "payment-service",
            gap_type=GapType.MISSING_TRACES,
            severity=GapSeverity.CRITICAL,
            coverage=CoverageLevel.NONE,
            coverage_pct=10.0,
            details="No distributed traces configured",
        )
        assert r.severity == GapSeverity.CRITICAL
        assert r.coverage == CoverageLevel.NONE
        assert r.coverage_pct == 10.0
        assert r.details == "No distributed traces configured"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_gap(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_gap
# -------------------------------------------------------------------


class TestGetGap:
    def test_found(self):
        eng = _engine()
        r = eng.record_gap("api-gateway")
        assert eng.get_gap(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_gap("nonexistent") is None


# -------------------------------------------------------------------
# list_gaps
# -------------------------------------------------------------------


class TestListGaps:
    def test_list_all(self):
        eng = _engine()
        eng.record_gap("svc-a")
        eng.record_gap("svc-b")
        assert len(eng.list_gaps()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_gap("svc-a")
        eng.record_gap("svc-b")
        results = eng.list_gaps(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_gap_type(self):
        eng = _engine()
        eng.record_gap("svc-a", gap_type=GapType.MISSING_METRICS)
        eng.record_gap("svc-b", gap_type=GapType.MISSING_TRACES)
        results = eng.list_gaps(gap_type=GapType.MISSING_TRACES)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_assessment
# -------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            "metrics-review",
            gap_type=GapType.MISSING_METRICS,
            severity=GapSeverity.HIGH,
            target_coverage_pct=95.0,
            review_interval_days=14,
        )
        assert a.assessment_name == "metrics-review"
        assert a.gap_type == GapType.MISSING_METRICS
        assert a.target_coverage_pct == 95.0
        assert a.review_interval_days == 14

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_assessment(f"assessment-{i}")
        assert len(eng._assessments) == 2


# -------------------------------------------------------------------
# analyze_coverage_gaps
# -------------------------------------------------------------------


class TestAnalyzeCoverageGaps:
    def test_with_data(self):
        eng = _engine(min_coverage_pct=80.0)
        eng.record_gap("svc-a", coverage_pct=90.0)
        eng.record_gap("svc-a", coverage_pct=70.0)
        eng.record_gap("svc-a", coverage_pct=80.0)
        result = eng.analyze_coverage_gaps("svc-a")
        assert result["avg_coverage"] == 80.0
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_coverage_gaps("unknown-svc")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(min_coverage_pct=80.0)
        eng.record_gap("svc-a", coverage_pct=85.0)
        eng.record_gap("svc-a", coverage_pct=90.0)
        result = eng.analyze_coverage_gaps("svc-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_critical_gaps
# -------------------------------------------------------------------


class TestIdentifyCriticalGaps:
    def test_with_critical(self):
        eng = _engine()
        eng.record_gap("svc-a", severity=GapSeverity.CRITICAL)
        eng.record_gap("svc-a", severity=GapSeverity.HIGH)
        eng.record_gap("svc-b", severity=GapSeverity.LOW)
        results = eng.identify_critical_gaps()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["critical_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_gaps() == []

    def test_single_critical_not_returned(self):
        eng = _engine()
        eng.record_gap("svc-a", severity=GapSeverity.CRITICAL)
        assert eng.identify_critical_gaps() == []


# -------------------------------------------------------------------
# rank_by_gap_severity
# -------------------------------------------------------------------


class TestRankByGapSeverity:
    def test_with_data(self):
        eng = _engine()
        eng.record_gap("svc-a", coverage_pct=90.0)
        eng.record_gap("svc-b", coverage_pct=20.0)
        results = eng.rank_by_gap_severity()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_coverage_pct"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_gap_severity() == []


# -------------------------------------------------------------------
# detect_coverage_trends
# -------------------------------------------------------------------


class TestDetectCoverageTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_gap("svc-a")
        eng.record_gap("svc-b")
        results = eng.detect_coverage_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_coverage_trends() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_gap("svc-a")
        assert eng.detect_coverage_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_gap("svc-a", severity=GapSeverity.CRITICAL)
        eng.record_gap("svc-b", severity=GapSeverity.LOW)
        eng.add_assessment("assessment-1")
        report = eng.generate_report()
        assert report.total_gaps == 2
        assert report.total_assessments == 1
        assert report.critical_count == 1
        assert report.by_gap_type != {}
        assert report.by_severity != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_gaps == 0
        assert report.coverage_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_gap("svc-a")
        eng.add_assessment("assessment-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_gaps"] == 0
        assert stats["total_assessments"] == 0
        assert stats["gap_type_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_coverage_pct=85.0)
        eng.record_gap("svc-a", gap_type=GapType.MISSING_METRICS)
        eng.record_gap("svc-b", gap_type=GapType.MISSING_TRACES)
        eng.add_assessment("assessment-1")
        stats = eng.get_stats()
        assert stats["total_gaps"] == 2
        assert stats["total_assessments"] == 1
        assert stats["unique_services"] == 2
        assert stats["min_coverage_pct"] == 85.0
