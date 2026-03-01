"""Tests for shieldops.observability.trace_coverage — TraceCoverageAnalyzer."""

from __future__ import annotations

from shieldops.observability.trace_coverage import (
    CoverageGap,
    CoverageLevel,
    CoverageMetric,
    InstrumentationType,
    TraceCoverageAnalyzer,
    TraceCoverageRecord,
    TraceCoverageReport,
)


def _engine(**kw) -> TraceCoverageAnalyzer:
    return TraceCoverageAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_level_full(self):
        assert CoverageLevel.FULL == "full"

    def test_level_high(self):
        assert CoverageLevel.HIGH == "high"

    def test_level_partial(self):
        assert CoverageLevel.PARTIAL == "partial"

    def test_level_low(self):
        assert CoverageLevel.LOW == "low"

    def test_level_none(self):
        assert CoverageLevel.NONE == "none"

    def test_instrumentation_auto(self):
        assert InstrumentationType.AUTO_INSTRUMENTED == "auto_instrumented"

    def test_instrumentation_manual(self):
        assert InstrumentationType.MANUAL_INSTRUMENTED == "manual_instrumented"

    def test_instrumentation_hybrid(self):
        assert InstrumentationType.HYBRID == "hybrid"

    def test_instrumentation_legacy(self):
        assert InstrumentationType.LEGACY == "legacy"

    def test_instrumentation_uninstrumented(self):
        assert InstrumentationType.UNINSTRUMENTED == "uninstrumented"

    def test_gap_missing_spans(self):
        assert CoverageGap.MISSING_SPANS == "missing_spans"

    def test_gap_incomplete_context(self):
        assert CoverageGap.INCOMPLETE_CONTEXT == "incomplete_context"

    def test_gap_no_attributes(self):
        assert CoverageGap.NO_ATTRIBUTES == "no_attributes"

    def test_gap_broken_propagation(self):
        assert CoverageGap.BROKEN_PROPAGATION == "broken_propagation"

    def test_gap_sampling_loss(self):
        assert CoverageGap.SAMPLING_LOSS == "sampling_loss"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_trace_coverage_record_defaults(self):
        r = TraceCoverageRecord()
        assert r.id
        assert r.service_id == ""
        assert r.coverage_level == CoverageLevel.NONE
        assert r.instrumentation_type == InstrumentationType.UNINSTRUMENTED
        assert r.coverage_gap == CoverageGap.MISSING_SPANS
        assert r.coverage_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_coverage_metric_defaults(self):
        m = CoverageMetric()
        assert m.id
        assert m.service_id == ""
        assert m.coverage_level == CoverageLevel.NONE
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_trace_coverage_report_defaults(self):
        r = TraceCoverageReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.low_coverage_count == 0
        assert r.avg_coverage_score == 0.0
        assert r.by_coverage_level == {}
        assert r.by_instrumentation == {}
        assert r.by_gap == {}
        assert r.top_uncovered == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_coverage
# ---------------------------------------------------------------------------


class TestRecordCoverage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_coverage(
            service_id="SVC-001",
            coverage_level=CoverageLevel.FULL,
            instrumentation_type=InstrumentationType.AUTO_INSTRUMENTED,
            coverage_gap=CoverageGap.MISSING_SPANS,
            coverage_score=95.0,
            service="api-gateway",
            team="sre",
        )
        assert r.service_id == "SVC-001"
        assert r.coverage_level == CoverageLevel.FULL
        assert r.instrumentation_type == InstrumentationType.AUTO_INSTRUMENTED
        assert r.coverage_gap == CoverageGap.MISSING_SPANS
        assert r.coverage_score == 95.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_coverage(service_id=f"SVC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_coverage
# ---------------------------------------------------------------------------


class TestGetCoverage:
    def test_found(self):
        eng = _engine()
        r = eng.record_coverage(
            service_id="SVC-001",
            coverage_score=85.0,
        )
        result = eng.get_coverage(r.id)
        assert result is not None
        assert result.coverage_score == 85.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_coverage("nonexistent") is None


# ---------------------------------------------------------------------------
# list_coverages
# ---------------------------------------------------------------------------


class TestListCoverages:
    def test_list_all(self):
        eng = _engine()
        eng.record_coverage(service_id="SVC-001")
        eng.record_coverage(service_id="SVC-002")
        assert len(eng.list_coverages()) == 2

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_coverage(
            service_id="SVC-001",
            coverage_level=CoverageLevel.FULL,
        )
        eng.record_coverage(
            service_id="SVC-002",
            coverage_level=CoverageLevel.LOW,
        )
        results = eng.list_coverages(level=CoverageLevel.FULL)
        assert len(results) == 1

    def test_filter_by_instrumentation(self):
        eng = _engine()
        eng.record_coverage(
            service_id="SVC-001",
            instrumentation_type=InstrumentationType.AUTO_INSTRUMENTED,
        )
        eng.record_coverage(
            service_id="SVC-002",
            instrumentation_type=InstrumentationType.LEGACY,
        )
        results = eng.list_coverages(
            instrumentation=InstrumentationType.AUTO_INSTRUMENTED,
        )
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_coverage(service_id="SVC-001", service="api-gw")
        eng.record_coverage(service_id="SVC-002", service="auth-svc")
        results = eng.list_coverages(service="api-gw")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_coverage(service_id="SVC-001", team="sre")
        eng.record_coverage(service_id="SVC-002", team="platform")
        results = eng.list_coverages(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_coverage(service_id=f"SVC-{i}")
        assert len(eng.list_coverages(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            service_id="SVC-001",
            coverage_level=CoverageLevel.HIGH,
            metric_score=0.92,
            threshold=0.8,
            breached=True,
            description="Coverage above threshold",
        )
        assert m.service_id == "SVC-001"
        assert m.coverage_level == CoverageLevel.HIGH
        assert m.metric_score == 0.92
        assert m.threshold == 0.8
        assert m.breached is True
        assert m.description == "Coverage above threshold"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(service_id=f"SVC-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_coverage_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCoverageDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_coverage(
            service_id="SVC-001",
            coverage_level=CoverageLevel.FULL,
            coverage_score=95.0,
        )
        eng.record_coverage(
            service_id="SVC-002",
            coverage_level=CoverageLevel.FULL,
            coverage_score=90.0,
        )
        result = eng.analyze_coverage_distribution()
        assert "full" in result
        assert result["full"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_coverage_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_coverage_services
# ---------------------------------------------------------------------------


class TestIdentifyLowCoverageServices:
    def test_detects_low_coverage(self):
        eng = _engine()
        eng.record_coverage(
            service_id="SVC-001",
            coverage_level=CoverageLevel.LOW,
        )
        eng.record_coverage(
            service_id="SVC-002",
            coverage_level=CoverageLevel.FULL,
        )
        results = eng.identify_low_coverage_services()
        assert len(results) == 1
        assert results[0]["service_id"] == "SVC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_coverage_services() == []


# ---------------------------------------------------------------------------
# rank_by_coverage_score
# ---------------------------------------------------------------------------


class TestRankByCoverageScore:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_coverage(
            service_id="SVC-001",
            service="api-gw",
            coverage_score=30.0,
        )
        eng.record_coverage(
            service_id="SVC-002",
            service="api-gw",
            coverage_score=40.0,
        )
        eng.record_coverage(
            service_id="SVC-003",
            service="auth-svc",
            coverage_score=90.0,
        )
        results = eng.rank_by_coverage_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_coverage_score"] == 35.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_coverage_score() == []


# ---------------------------------------------------------------------------
# detect_coverage_trends
# ---------------------------------------------------------------------------


class TestDetectCoverageTrends:
    def test_stable(self):
        eng = _engine()
        for score in [50.0, 50.0, 50.0, 50.0]:
            eng.add_metric(
                service_id="SVC-001",
                metric_score=score,
            )
        result = eng.detect_coverage_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for score in [30.0, 30.0, 80.0, 80.0]:
            eng.add_metric(
                service_id="SVC-001",
                metric_score=score,
            )
        result = eng.detect_coverage_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_coverage_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_coverage(
            service_id="SVC-001",
            coverage_level=CoverageLevel.LOW,
            instrumentation_type=InstrumentationType.LEGACY,
            coverage_gap=CoverageGap.MISSING_SPANS,
            coverage_score=25.0,
            service="api-gw",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, TraceCoverageReport)
        assert report.total_records == 1
        assert report.low_coverage_count == 1
        assert report.avg_coverage_score == 25.0
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
        eng.record_coverage(service_id="SVC-001")
        eng.add_metric(service_id="SVC-001")
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
        assert stats["coverage_level_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_coverage(
            service_id="SVC-001",
            coverage_level=CoverageLevel.FULL,
            service="api-gw",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "full" in stats["coverage_level_distribution"]
