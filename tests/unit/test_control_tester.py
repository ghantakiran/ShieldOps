"""Tests for shieldops.compliance.control_tester — ComplianceControlTester."""

from __future__ import annotations

from shieldops.compliance.control_tester import (
    ComplianceControlReport,
    ComplianceControlTester,
    ControlTestEvidence,
    ControlTestFrequency,
    ControlTestRecord,
    ControlTestResult,
    ControlType,
)


def _engine(**kw) -> ComplianceControlTester:
    return ComplianceControlTester(**kw)


class TestEnums:
    def test_result_pass(self):
        assert ControlTestResult.PASS == "pass"  # noqa: S105

    def test_result_partial_pass(self):
        assert ControlTestResult.PARTIAL_PASS == "partial_pass"  # noqa: S105

    def test_result_fail(self):
        assert ControlTestResult.FAIL == "fail"

    def test_result_error(self):
        assert ControlTestResult.ERROR == "error"

    def test_result_skipped(self):
        assert ControlTestResult.SKIPPED == "skipped"

    def test_type_preventive(self):
        assert ControlType.PREVENTIVE == "preventive"

    def test_type_detective(self):
        assert ControlType.DETECTIVE == "detective"

    def test_type_corrective(self):
        assert ControlType.CORRECTIVE == "corrective"

    def test_type_compensating(self):
        assert ControlType.COMPENSATING == "compensating"

    def test_type_administrative(self):
        assert ControlType.ADMINISTRATIVE == "administrative"

    def test_frequency_daily(self):
        assert ControlTestFrequency.DAILY == "daily"

    def test_frequency_weekly(self):
        assert ControlTestFrequency.WEEKLY == "weekly"

    def test_frequency_monthly(self):
        assert ControlTestFrequency.MONTHLY == "monthly"

    def test_frequency_quarterly(self):
        assert ControlTestFrequency.QUARTERLY == "quarterly"

    def test_frequency_annually(self):
        assert ControlTestFrequency.ANNUALLY == "annually"


class TestModels:
    def test_control_test_record_defaults(self):
        r = ControlTestRecord()
        assert r.id
        assert r.control_id == ""
        assert r.result == ControlTestResult.PASS
        assert r.control_type == ControlType.PREVENTIVE
        assert r.frequency == ControlTestFrequency.MONTHLY
        assert r.pass_rate_pct == 0.0
        assert r.framework == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_test_evidence_defaults(self):
        e = ControlTestEvidence()
        assert e.id
        assert e.test_record_id == ""
        assert e.evidence_type == ""
        assert e.description == ""
        assert e.verified is False
        assert e.created_at > 0

    def test_report_defaults(self):
        r = ComplianceControlReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_evidence == 0
        assert r.overall_pass_rate_pct == 0.0
        assert r.failing_controls == 0
        assert r.by_result == {}
        assert r.by_control_type == {}
        assert r.by_frequency == {}
        assert r.critical_failures == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecordTest:
    def test_basic(self):
        eng = _engine()
        r = eng.record_test("ctrl-1", pass_rate_pct=95.0)
        assert r.control_id == "ctrl-1"
        assert r.pass_rate_pct == 95.0

    def test_with_result(self):
        eng = _engine()
        r = eng.record_test("ctrl-2", result=ControlTestResult.FAIL)
        assert r.result == ControlTestResult.FAIL

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_test(f"ctrl-{i}")
        assert len(eng._records) == 3


class TestGetTest:
    def test_found(self):
        eng = _engine()
        r = eng.record_test("ctrl-1")
        assert eng.get_test(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_test("nonexistent") is None


class TestListTests:
    def test_list_all(self):
        eng = _engine()
        eng.record_test("ctrl-1")
        eng.record_test("ctrl-2")
        assert len(eng.list_tests()) == 2

    def test_filter_by_result(self):
        eng = _engine()
        eng.record_test("ctrl-1", result=ControlTestResult.PASS)
        eng.record_test("ctrl-2", result=ControlTestResult.FAIL)
        results = eng.list_tests(result=ControlTestResult.PASS)
        assert len(results) == 1

    def test_filter_by_control_type(self):
        eng = _engine()
        eng.record_test("ctrl-1", control_type=ControlType.DETECTIVE)
        eng.record_test("ctrl-2", control_type=ControlType.PREVENTIVE)
        results = eng.list_tests(control_type=ControlType.DETECTIVE)
        assert len(results) == 1

    def test_filter_by_framework(self):
        eng = _engine()
        eng.record_test("ctrl-1", framework="SOC2")
        eng.record_test("ctrl-2", framework="ISO27001")
        results = eng.list_tests(framework="SOC2")
        assert len(results) == 1


class TestAddEvidence:
    def test_basic(self):
        eng = _engine()
        e = eng.add_evidence("rec-1", evidence_type="screenshot", verified=True)
        assert e.test_record_id == "rec-1"
        assert e.evidence_type == "screenshot"
        assert e.verified is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_evidence(f"rec-{i}")
        assert len(eng._evidence) == 2


class TestAnalyzeControlTestResults:
    def test_with_data(self):
        eng = _engine()
        eng.record_test("c1", control_type=ControlType.DETECTIVE, pass_rate_pct=80.0)
        eng.record_test(
            "c2",
            control_type=ControlType.DETECTIVE,
            pass_rate_pct=60.0,
            result=ControlTestResult.FAIL,
        )
        result = eng.analyze_test_results()
        assert "detective" in result
        assert result["detective"]["count"] == 2
        assert result["detective"]["pass_count"] == 1

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_test_results() == {}


class TestIdentifyFailingControls:
    def test_with_failing(self):
        eng = _engine(min_pass_rate_pct=90.0)
        eng.record_test("ctrl-low", pass_rate_pct=70.0)
        eng.record_test("ctrl-high", pass_rate_pct=95.0)
        results = eng.identify_failing_controls()
        assert len(results) == 1
        assert results[0]["control_id"] == "ctrl-low"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failing_controls() == []


class TestRankByPassRate:
    def test_ascending_order(self):
        eng = _engine()
        eng.record_test("c1", framework="SOC2", pass_rate_pct=60.0)
        eng.record_test("c2", framework="ISO27001", pass_rate_pct=95.0)
        results = eng.rank_by_pass_rate()
        assert results[0]["framework"] == "SOC2"
        assert results[0]["avg_pass_rate_pct"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_pass_rate() == []


class TestDetectTestTrends:
    def test_improving(self):
        eng = _engine()
        for rate in [50.0, 50.0, 95.0, 95.0]:
            eng.record_test("c", pass_rate_pct=rate)
        result = eng.detect_test_trends()
        assert result["trend"] == "improving"

    def test_worsening(self):
        eng = _engine()
        for rate in [95.0, 95.0, 50.0, 50.0]:
            eng.record_test("c", pass_rate_pct=rate)
        result = eng.detect_test_trends()
        assert result["trend"] == "worsening"

    def test_insufficient_data(self):
        eng = _engine()
        eng.record_test("c1", pass_rate_pct=80.0)
        result = eng.detect_test_trends()
        assert result["status"] == "insufficient_data"


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_pass_rate_pct=90.0)
        eng.record_test("ctrl-bad", pass_rate_pct=50.0, result=ControlTestResult.FAIL)
        eng.record_test("ctrl-ok", pass_rate_pct=95.0, result=ControlTestResult.PASS)
        eng.add_evidence("rec-1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_evidence == 1
        assert report.failing_controls == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_test("ctrl-1")
        eng.add_evidence("rec-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._evidence) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_evidence"] == 0
        assert stats["result_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_test("ctrl-1", result=ControlTestResult.PASS, framework="SOC2")
        eng.record_test("ctrl-2", result=ControlTestResult.FAIL, framework="ISO27001")
        eng.add_evidence("rec-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_evidence"] == 1
        assert stats["unique_frameworks"] == 2
