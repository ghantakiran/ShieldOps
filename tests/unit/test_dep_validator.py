"""Tests for shieldops.topology.dep_validator — ServiceDependencyValidator."""

from __future__ import annotations

from shieldops.topology.dep_validator import (
    DependencyDirection,
    DependencyValidationReport,
    ServiceDependencyValidator,
    ValidationRecord,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
)


def _engine(**kw) -> ServiceDependencyValidator:
    return ServiceDependencyValidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_result_valid(self):
        assert ValidationResult.VALID == "valid"

    def test_result_invalid(self):
        assert ValidationResult.INVALID == "invalid"

    def test_result_undeclared(self):
        assert ValidationResult.UNDECLARED == "undeclared"

    def test_result_stale(self):
        assert ValidationResult.STALE == "stale"

    def test_result_partial(self):
        assert ValidationResult.PARTIAL == "partial"

    def test_direction_upstream(self):
        assert DependencyDirection.UPSTREAM == "upstream"

    def test_direction_downstream(self):
        assert DependencyDirection.DOWNSTREAM == "downstream"

    def test_direction_bidirectional(self):
        assert DependencyDirection.BIDIRECTIONAL == "bidirectional"

    def test_direction_circular(self):
        assert DependencyDirection.CIRCULAR == "circular"

    def test_direction_unknown(self):
        assert DependencyDirection.UNKNOWN == "unknown"

    def test_severity_critical(self):
        assert ValidationSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert ValidationSeverity.HIGH == "high"

    def test_severity_moderate(self):
        assert ValidationSeverity.MODERATE == "moderate"

    def test_severity_low(self):
        assert ValidationSeverity.LOW == "low"

    def test_severity_info(self):
        assert ValidationSeverity.INFO == "info"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_validation_record_defaults(self):
        r = ValidationRecord()
        assert r.id
        assert r.service == ""
        assert r.dependency == ""
        assert r.result == ValidationResult.VALID
        assert r.direction == DependencyDirection.UNKNOWN
        assert r.severity == ValidationSeverity.INFO
        assert r.team == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_validation_rule_defaults(self):
        ru = ValidationRule()
        assert ru.id
        assert ru.service_pattern == ""
        assert ru.result == ValidationResult.VALID
        assert ru.direction == DependencyDirection.UNKNOWN
        assert ru.threshold_pct == 0.0
        assert ru.reason == ""
        assert ru.created_at > 0

    def test_report_defaults(self):
        r = DependencyValidationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.invalid_count == 0
        assert r.undeclared_count == 0
        assert r.by_result == {}
        assert r.by_direction == {}
        assert r.by_severity == {}
        assert r.high_risk_services == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_validation
# ---------------------------------------------------------------------------


class TestRecordValidation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_validation(
            service="api-gw",
            dependency="auth-svc",
            result=ValidationResult.INVALID,
            direction=DependencyDirection.UPSTREAM,
            severity=ValidationSeverity.HIGH,
            team="platform",
        )
        assert r.service == "api-gw"
        assert r.dependency == "auth-svc"
        assert r.result == ValidationResult.INVALID
        assert r.direction == DependencyDirection.UPSTREAM
        assert r.severity == ValidationSeverity.HIGH
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_validation(service=f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_validation
# ---------------------------------------------------------------------------


class TestGetValidation:
    def test_found(self):
        eng = _engine()
        r = eng.record_validation(
            service="api-gw",
            severity=ValidationSeverity.CRITICAL,
        )
        result = eng.get_validation(r.id)
        assert result is not None
        assert result.severity == ValidationSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_validation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_validations
# ---------------------------------------------------------------------------


class TestListValidations:
    def test_list_all(self):
        eng = _engine()
        eng.record_validation(service="svc-a")
        eng.record_validation(service="svc-b")
        assert len(eng.list_validations()) == 2

    def test_filter_by_result(self):
        eng = _engine()
        eng.record_validation(
            service="svc-a",
            result=ValidationResult.VALID,
        )
        eng.record_validation(
            service="svc-b",
            result=ValidationResult.INVALID,
        )
        results = eng.list_validations(result=ValidationResult.VALID)
        assert len(results) == 1

    def test_filter_by_direction(self):
        eng = _engine()
        eng.record_validation(
            service="svc-a",
            direction=DependencyDirection.UPSTREAM,
        )
        eng.record_validation(
            service="svc-b",
            direction=DependencyDirection.DOWNSTREAM,
        )
        results = eng.list_validations(direction=DependencyDirection.UPSTREAM)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_validation(service="svc-a", team="sre")
        eng.record_validation(service="svc-b", team="platform")
        results = eng.list_validations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_validation(service=f"svc-{i}")
        assert len(eng.list_validations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        ru = eng.add_rule(
            service_pattern="api-*",
            result=ValidationResult.INVALID,
            direction=DependencyDirection.UPSTREAM,
            threshold_pct=15.0,
            reason="high traffic",
        )
        assert ru.service_pattern == "api-*"
        assert ru.result == ValidationResult.INVALID
        assert ru.threshold_pct == 15.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(service_pattern=f"svc-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_validation_results
# ---------------------------------------------------------------------------


class TestAnalyzeValidationResults:
    def test_with_data(self):
        eng = _engine()
        eng.record_validation(
            service="svc-a",
            result=ValidationResult.VALID,
            severity=ValidationSeverity.HIGH,
        )
        eng.record_validation(
            service="svc-b",
            result=ValidationResult.VALID,
            severity=ValidationSeverity.LOW,
        )
        result = eng.analyze_validation_results()
        assert "valid" in result
        assert result["valid"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_validation_results() == {}


# ---------------------------------------------------------------------------
# identify_undeclared_deps
# ---------------------------------------------------------------------------


class TestIdentifyUndeclaredDeps:
    def test_detects_undeclared(self):
        eng = _engine()
        eng.record_validation(
            service="svc-a",
            result=ValidationResult.UNDECLARED,
        )
        eng.record_validation(
            service="svc-b",
            result=ValidationResult.VALID,
        )
        results = eng.identify_undeclared_deps()
        assert len(results) == 1
        assert results[0]["service"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_undeclared_deps() == []


# ---------------------------------------------------------------------------
# rank_by_invalid_count
# ---------------------------------------------------------------------------


class TestRankByInvalidCount:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_validation(
            service="svc-a",
            result=ValidationResult.INVALID,
        )
        eng.record_validation(
            service="svc-a",
            result=ValidationResult.INVALID,
        )
        eng.record_validation(
            service="svc-b",
            result=ValidationResult.INVALID,
        )
        results = eng.rank_by_invalid_count()
        assert len(results) == 2
        assert results[0]["service"] == "svc-a"
        assert results[0]["invalid_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_invalid_count() == []


# ---------------------------------------------------------------------------
# detect_validation_trends
# ---------------------------------------------------------------------------


class TestDetectValidationTrends:
    def test_stable(self):
        eng = _engine()
        for pct in [10.0, 10.0, 10.0, 10.0]:
            eng.add_rule(
                service_pattern="s",
                threshold_pct=pct,
            )
        result = eng.detect_validation_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for pct in [5.0, 5.0, 20.0, 20.0]:
            eng.add_rule(
                service_pattern="s",
                threshold_pct=pct,
            )
        result = eng.detect_validation_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_validation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_validation(
            service="svc-a",
            result=ValidationResult.UNDECLARED,
            severity=ValidationSeverity.HIGH,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, DependencyValidationReport)
        assert report.total_records == 1
        assert report.undeclared_count == 1
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
        eng.record_validation(service="svc-a")
        eng.add_rule(service_pattern="svc-*")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["result_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_validation(
            service="api-gw",
            result=ValidationResult.INVALID,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "invalid" in stats["result_distribution"]
