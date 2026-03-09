"""Tests for shieldops.observability.trace_driven_testing — TraceDrivenTesting."""

from __future__ import annotations

from shieldops.observability.trace_driven_testing import (
    CoverageLevel,
    GeneratedTestCase,
    TraceCoverageReport,
    TraceDrivenTesting,
    TraceRecord,
    TraceStatus,
    TraceTestType,
)


def _engine(**kw) -> TraceDrivenTesting:
    return TraceDrivenTesting(**kw)


class TestEnums:
    def test_trace_status_success(self):
        assert TraceStatus.SUCCESS == "success"

    def test_trace_status_error(self):
        assert TraceStatus.ERROR == "error"

    def test_trace_status_timeout(self):
        assert TraceStatus.TIMEOUT == "timeout"

    def test_trace_status_partial(self):
        assert TraceStatus.PARTIAL == "partial"

    def test_test_type_integration(self):
        assert TraceTestType.INTEGRATION == "integration"

    def test_test_type_contract(self):
        assert TraceTestType.CONTRACT == "contract"

    def test_test_type_load(self):
        assert TraceTestType.LOAD == "load"

    def test_test_type_regression(self):
        assert TraceTestType.REGRESSION == "regression"

    def test_coverage_full(self):
        assert CoverageLevel.FULL == "full"

    def test_coverage_partial(self):
        assert CoverageLevel.PARTIAL == "partial"

    def test_coverage_none(self):
        assert CoverageLevel.NONE == "none"


class TestModels:
    def test_trace_record_defaults(self):
        r = TraceRecord()
        assert r.id
        assert r.status == TraceStatus.SUCCESS
        assert r.span_count == 1
        assert r.tags == {}

    def test_generated_test_defaults(self):
        t = GeneratedTestCase()
        assert t.id
        assert t.test_type == TraceTestType.INTEGRATION

    def test_coverage_report_defaults(self):
        r = TraceCoverageReport()
        assert r.total_traces == 0
        assert r.coverage_level == CoverageLevel.NONE


class TestAddTrace:
    def test_basic(self):
        eng = _engine()
        t = eng.add_trace("t1", "auth", "login", duration_ms=50.0)
        assert t.trace_id == "t1"
        assert t.service == "auth"
        assert t.operation == "login"

    def test_with_tags(self):
        eng = _engine()
        t = eng.add_trace("t1", "auth", "login", tags={"env": "prod"})
        assert t.tags == {"env": "prod"}

    def test_eviction(self):
        eng = _engine(max_traces=3)
        for i in range(5):
            eng.add_trace(f"t-{i}", "svc", "op")
        assert len(eng._traces) == 3


class TestExtractTestCases:
    def test_basic(self):
        eng = _engine()
        eng.add_trace("t1", "auth", "login")
        eng.add_trace("t2", "auth", "logout")
        tests = eng.extract_test_cases()
        assert len(tests) == 2

    def test_dedup(self):
        eng = _engine()
        eng.add_trace("t1", "auth", "login")
        eng.add_trace("t2", "auth", "login")
        tests = eng.extract_test_cases()
        assert len(tests) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.add_trace("t1", "auth", "login")
        eng.add_trace("t2", "api", "get")
        tests = eng.extract_test_cases(service="auth")
        assert len(tests) == 1

    def test_custom_type(self):
        eng = _engine()
        eng.add_trace("t1", "auth", "login")
        tests = eng.extract_test_cases(test_type=TraceTestType.CONTRACT)
        assert tests[0].test_type == TraceTestType.CONTRACT

    def test_empty(self):
        eng = _engine()
        assert eng.extract_test_cases() == []


class TestGenerateSyntheticTraces:
    def test_basic(self):
        eng = _engine()
        traces = eng.generate_synthetic_traces("auth", "login", count=5)
        assert len(traces) == 5
        assert all(t.service == "auth" for t in traces)

    def test_default_count(self):
        eng = _engine()
        traces = eng.generate_synthetic_traces("auth", "login")
        assert len(traces) == 10

    def test_based_on_existing(self):
        eng = _engine()
        eng.add_trace("t1", "auth", "login", duration_ms=100.0)
        traces = eng.generate_synthetic_traces("auth", "login", count=3)
        assert len(traces) == 3


class TestValidateTraceCoverage:
    def test_empty(self):
        eng = _engine()
        result = eng.validate_trace_coverage()
        assert result["coverage_pct"] == 0

    def test_full_coverage(self):
        eng = _engine()
        eng.add_trace("t1", "auth", "login")
        eng.extract_test_cases()
        result = eng.validate_trace_coverage()
        assert result["coverage_pct"] == 100.0
        assert result["coverage_level"] == "full"

    def test_partial_coverage(self):
        eng = _engine()
        eng.add_trace("t1", "auth", "login")
        eng.add_trace("t2", "auth", "logout")
        eng.add_trace("t3", "api", "get")
        eng.extract_test_cases(service="auth")
        result = eng.validate_trace_coverage()
        assert 0 < result["coverage_pct"] < 100


class TestCompareTracePatterns:
    def test_no_data(self):
        eng = _engine()
        result = eng.compare_trace_patterns("auth", "login")
        assert result["samples"] == 0

    def test_with_data(self):
        eng = _engine()
        eng.add_trace("t1", "auth", "login", duration_ms=50.0)
        eng.add_trace("t2", "auth", "login", duration_ms=100.0)
        result = eng.compare_trace_patterns("auth", "login")
        assert result["samples"] == 2
        assert result["avg_duration_ms"] == 75.0

    def test_error_rate(self):
        eng = _engine()
        eng.add_trace("t1", "auth", "login", status=TraceStatus.SUCCESS)
        eng.add_trace("t2", "auth", "login", status=TraceStatus.ERROR)
        result = eng.compare_trace_patterns("auth", "login")
        assert result["error_rate"] == 0.5


class TestGetCoverageReport:
    def test_empty(self):
        eng = _engine()
        report = eng.get_coverage_report()
        assert report.total_traces == 0

    def test_populated(self):
        eng = _engine()
        eng.add_trace("t1", "auth", "login")
        eng.extract_test_cases()
        report = eng.get_coverage_report()
        assert report.total_traces == 1
        assert report.total_tests == 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.add_trace("t1", "auth", "login")
        eng.extract_test_cases()
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._traces) == 0
        assert len(eng._tests) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_traces"] == 0

    def test_populated(self):
        eng = _engine()
        eng.add_trace("t1", "auth", "login")
        eng.add_trace("t2", "api", "get")
        stats = eng.get_stats()
        assert stats["unique_services"] == 2
        assert stats["unique_operations"] == 2
