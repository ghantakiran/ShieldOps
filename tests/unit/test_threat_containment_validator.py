"""Tests for shieldops.security.threat_containment_validator — ThreatContainmentValidator."""

from __future__ import annotations

from shieldops.security.threat_containment_validator import (
    ThreatContainmentValidator,
    ValidationAnalysis,
    ValidationCheck,
    ValidationRecord,
    ValidationReport,
    ValidationResult,
    ValidationSeverity,
)


def _engine(**kw) -> ThreatContainmentValidator:
    return ThreatContainmentValidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_validationcheck_val1(self):
        assert ValidationCheck.NETWORK_ISOLATED == "network_isolated"

    def test_validationcheck_val2(self):
        assert ValidationCheck.PROCESS_TERMINATED == "process_terminated"

    def test_validationcheck_val3(self):
        assert ValidationCheck.CREDENTIALS_ROTATED == "credentials_rotated"

    def test_validationcheck_val4(self):
        assert ValidationCheck.ARTIFACTS_REMOVED == "artifacts_removed"

    def test_validationcheck_val5(self):
        assert ValidationCheck.SERVICES_HEALTHY == "services_healthy"

    def test_validationresult_val1(self):
        assert ValidationResult.PASSED == "passed"

    def test_validationresult_val2(self):
        assert ValidationResult.FAILED == "failed"

    def test_validationresult_val3(self):
        assert ValidationResult.PARTIAL == "partial"

    def test_validationresult_val4(self):
        assert ValidationResult.SKIPPED == "skipped"

    def test_validationresult_val5(self):
        assert ValidationResult.TIMEOUT == "timeout"

    def test_validationseverity_val1(self):
        assert ValidationSeverity.CRITICAL == "critical"

    def test_validationseverity_val2(self):
        assert ValidationSeverity.HIGH == "high"

    def test_validationseverity_val3(self):
        assert ValidationSeverity.MEDIUM == "medium"

    def test_validationseverity_val4(self):
        assert ValidationSeverity.LOW == "low"

    def test_validationseverity_val5(self):
        assert ValidationSeverity.INFO == "info"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = ValidationRecord()
        assert r.id
        assert r.name == ""
        assert r.validation_check == ValidationCheck.NETWORK_ISOLATED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ValidationAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ValidationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_check == {}
        assert r.by_result == {}
        assert r.by_severity == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_validation(
            name="test",
            validation_check=ValidationCheck.PROCESS_TERMINATED,
            score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.name == "test"
        assert r.validation_check == ValidationCheck.PROCESS_TERMINATED
        assert r.score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_validation(name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_validation(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_validation(name="a")
        eng.record_validation(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_validation(name="a", validation_check=ValidationCheck.NETWORK_ISOLATED)
        eng.record_validation(name="b", validation_check=ValidationCheck.PROCESS_TERMINATED)
        results = eng.list_records(validation_check=ValidationCheck.NETWORK_ISOLATED)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_validation(name="a", validation_result=ValidationResult.PASSED)
        eng.record_validation(name="b", validation_result=ValidationResult.FAILED)
        results = eng.list_records(validation_result=ValidationResult.PASSED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_validation(name="a", team="sec")
        eng.record_validation(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_validation(name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_validation(
            name="a",
            validation_check=ValidationCheck.NETWORK_ISOLATED,
            score=90.0,
        )
        eng.record_validation(
            name="b",
            validation_check=ValidationCheck.NETWORK_ISOLATED,
            score=70.0,
        )
        result = eng.analyze_check_distribution()
        assert "network_isolated" in result
        assert result["network_isolated"]["count"] == 2
        assert result["network_isolated"]["avg_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_check_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(score_threshold=80.0)
        eng.record_validation(name="a", score=60.0)
        eng.record_validation(name="b", score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(score_threshold=80.0)
        eng.record_validation(name="a", score=50.0)
        eng.record_validation(name="b", score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_validation(name="a", service="auth-svc", score=90.0)
        eng.record_validation(name="b", service="api-gw", score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="t1", analysis_score=20.0)
        eng.add_analysis(name="t2", analysis_score=20.0)
        eng.add_analysis(name="t3", analysis_score=80.0)
        eng.add_analysis(name="t4", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(score_threshold=80.0)
        eng.record_validation(
            name="test",
            validation_check=ValidationCheck.PROCESS_TERMINATED,
            score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ValidationReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy range" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_validation(name="test")
        eng.add_analysis(name="test")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["check_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_validation(
            name="test",
            validation_check=ValidationCheck.NETWORK_ISOLATED,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "network_isolated" in stats["check_distribution"]
