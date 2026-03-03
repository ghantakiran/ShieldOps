"""Tests for shieldops.operations.auto_remediation_validator."""

from __future__ import annotations

from shieldops.operations.auto_remediation_validator import (
    AutoRemediationValidator,
    RemediationRisk,
    RemediationValidation,
    RemediationValidationReport,
    ValidationAnalysis,
    ValidationMethod,
    ValidationResult,
)


def _engine(**kw) -> AutoRemediationValidator:
    return AutoRemediationValidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_method_pre_check(self):
        assert ValidationMethod.PRE_CHECK == "pre_check"

    def test_method_post_check(self):
        assert ValidationMethod.POST_CHECK == "post_check"

    def test_method_smoke_test(self):
        assert ValidationMethod.SMOKE_TEST == "smoke_test"

    def test_method_health_check(self):
        assert ValidationMethod.HEALTH_CHECK == "health_check"

    def test_method_rollback_test(self):
        assert ValidationMethod.ROLLBACK_TEST == "rollback_test"

    def test_result_passed(self):
        assert ValidationResult.PASSED == "passed"  # noqa: S105

    def test_result_failed(self):
        assert ValidationResult.FAILED == "failed"

    def test_result_partial(self):
        assert ValidationResult.PARTIAL == "partial"

    def test_result_timeout(self):
        assert ValidationResult.TIMEOUT == "timeout"

    def test_result_skipped(self):
        assert ValidationResult.SKIPPED == "skipped"

    def test_risk_low(self):
        assert RemediationRisk.LOW == "low"

    def test_risk_medium(self):
        assert RemediationRisk.MEDIUM == "medium"

    def test_risk_high(self):
        assert RemediationRisk.HIGH == "high"

    def test_risk_critical(self):
        assert RemediationRisk.CRITICAL == "critical"

    def test_risk_unassessed(self):
        assert RemediationRisk.UNASSESSED == "unassessed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_remediation_validation_defaults(self):
        r = RemediationValidation()
        assert r.id
        assert r.validation_method == ValidationMethod.PRE_CHECK
        assert r.validation_result == ValidationResult.PASSED
        assert r.remediation_risk == RemediationRisk.LOW
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_validation_analysis_defaults(self):
        a = ValidationAnalysis()
        assert a.id
        assert a.validation_method == ValidationMethod.PRE_CHECK
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_remediation_validation_report_defaults(self):
        r = RemediationValidationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_method == {}
        assert r.by_result == {}
        assert r.by_risk == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        eng = _engine()
        assert eng._max_records == 200000
        assert eng._threshold == 50.0
        assert eng._records == []
        assert eng._analyses == []

    def test_custom_max_records(self):
        eng = _engine(max_records=8000)
        assert eng._max_records == 8000

    def test_custom_threshold(self):
        eng = _engine(threshold=75.0)
        assert eng._threshold == 75.0


# ---------------------------------------------------------------------------
# record_validation / get_validation
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_record_basic(self):
        eng = _engine()
        r = eng.record_validation(
            service="remediation-eng",
            validation_method=ValidationMethod.SMOKE_TEST,
            validation_result=ValidationResult.PASSED,
            remediation_risk=RemediationRisk.MEDIUM,
            score=88.0,
            team="sre",
        )
        assert r.service == "remediation-eng"
        assert r.validation_method == ValidationMethod.SMOKE_TEST
        assert r.validation_result == ValidationResult.PASSED
        assert r.remediation_risk == RemediationRisk.MEDIUM
        assert r.score == 88.0
        assert r.team == "sre"

    def test_record_stored(self):
        eng = _engine()
        eng.record_validation(service="svc-a")
        assert len(eng._records) == 1

    def test_get_found(self):
        eng = _engine()
        r = eng.record_validation(service="svc-a", score=74.0)
        result = eng.get_validation(r.id)
        assert result is not None
        assert result.score == 74.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_validation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_validations
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_validation(service="svc-a")
        eng.record_validation(service="svc-b")
        assert len(eng.list_validations()) == 2

    def test_filter_by_method(self):
        eng = _engine()
        eng.record_validation(service="svc-a", validation_method=ValidationMethod.PRE_CHECK)
        eng.record_validation(service="svc-b", validation_method=ValidationMethod.ROLLBACK_TEST)
        results = eng.list_validations(validation_method=ValidationMethod.PRE_CHECK)
        assert len(results) == 1

    def test_filter_by_result(self):
        eng = _engine()
        eng.record_validation(service="svc-a", validation_result=ValidationResult.PASSED)
        eng.record_validation(service="svc-b", validation_result=ValidationResult.FAILED)
        results = eng.list_validations(validation_result=ValidationResult.PASSED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_validation(service="svc-a", team="sre")
        eng.record_validation(service="svc-b", team="platform")
        assert len(eng.list_validations(team="sre")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_validation(service=f"svc-{i}")
        assert len(eng.list_validations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            validation_method=ValidationMethod.HEALTH_CHECK,
            analysis_score=42.0,
            threshold=50.0,
            breached=True,
            description="health check failed",
        )
        assert a.validation_method == ValidationMethod.HEALTH_CHECK
        assert a.analysis_score == 42.0
        assert a.breached is True

    def test_stored(self):
        eng = _engine()
        eng.add_analysis()
        assert len(eng._analyses) == 1

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _ in range(5):
            eng.add_analysis()
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_validation(
            service="s1", validation_method=ValidationMethod.PRE_CHECK, score=80.0
        )
        eng.record_validation(
            service="s2", validation_method=ValidationMethod.PRE_CHECK, score=60.0
        )
        result = eng.analyze_distribution()
        assert "pre_check" in result
        assert result["pre_check"]["count"] == 2
        assert result["pre_check"]["avg_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_validation_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_validation(service="svc-a", score=60.0)
        eng.record_validation(service="svc-b", score=90.0)
        results = eng.identify_validation_gaps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_validation(service="svc-a", score=55.0)
        eng.record_validation(service="svc-b", score=35.0)
        results = eng.identify_validation_gaps()
        assert results[0]["score"] == 35.0


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_validation(service="svc-a", score=90.0)
        eng.record_validation(service="svc-b", score=40.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "svc-b"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_score_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=20.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_score_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_score_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_validation(
            service="svc-a",
            validation_method=ValidationMethod.POST_CHECK,
            validation_result=ValidationResult.PARTIAL,
            remediation_risk=RemediationRisk.HIGH,
            score=45.0,
        )
        report = eng.generate_report()
        assert isinstance(report, RemediationValidationReport)
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
        eng.record_validation(service="svc-a")
        eng.add_analysis()
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_validation(
            service="svc-a",
            validation_method=ValidationMethod.PRE_CHECK,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert "pre_check" in stats["method_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_validation(service=f"svc-{i}")
        assert len(eng._records) == 3
