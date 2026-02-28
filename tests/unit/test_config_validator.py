"""Tests for shieldops.config.config_validator — ConfigValidationEngine."""

from __future__ import annotations

from shieldops.config.config_validator import (
    ConfigScope,
    ConfigValidationEngine,
    ConfigValidationReport,
    ValidationRecord,
    ValidationResult,
    ValidationRule,
    ValidationType,
)


def _engine(**kw) -> ConfigValidationEngine:
    return ConfigValidationEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ValidationType (5)
    def test_type_schema(self):
        assert ValidationType.SCHEMA == "schema"

    def test_type_consistency(self):
        assert ValidationType.CONSISTENCY == "consistency"

    def test_type_dependency(self):
        assert ValidationType.DEPENDENCY == "dependency"

    def test_type_security(self):
        assert ValidationType.SECURITY == "security"

    def test_type_performance(self):
        assert ValidationType.PERFORMANCE == "performance"

    # ValidationResult (5)
    def test_result_passed(self):
        assert ValidationResult.PASSED == "passed"

    def test_result_failed(self):
        assert ValidationResult.FAILED == "failed"

    def test_result_warning(self):
        assert ValidationResult.WARNING == "warning"

    def test_result_skipped(self):
        assert ValidationResult.SKIPPED == "skipped"

    def test_result_error(self):
        assert ValidationResult.ERROR == "error"

    # ConfigScope (5)
    def test_scope_application(self):
        assert ConfigScope.APPLICATION == "application"

    def test_scope_infrastructure(self):
        assert ConfigScope.INFRASTRUCTURE == "infrastructure"

    def test_scope_network(self):
        assert ConfigScope.NETWORK == "network"

    def test_scope_database(self):
        assert ConfigScope.DATABASE == "database"

    def test_scope_security(self):
        assert ConfigScope.SECURITY == "security"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_validation_record_defaults(self):
        r = ValidationRecord()
        assert r.id
        assert r.config_name == ""
        assert r.validation_type == ValidationType.SCHEMA
        assert r.result == ValidationResult.PASSED
        assert r.scope == ConfigScope.APPLICATION
        assert r.failure_rate_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_validation_rule_defaults(self):
        r = ValidationRule()
        assert r.id
        assert r.rule_name == ""
        assert r.validation_type == ValidationType.SCHEMA
        assert r.result == ValidationResult.PASSED
        assert r.scope == ConfigScope.APPLICATION
        assert r.max_allowed_failures == 3
        assert r.created_at > 0

    def test_config_validation_report_defaults(self):
        r = ConfigValidationReport()
        assert r.total_validations == 0
        assert r.total_rules == 0
        assert r.pass_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_result == {}
        assert r.failure_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_validation
# -------------------------------------------------------------------


class TestRecordValidation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_validation("app-config", validation_type=ValidationType.SCHEMA)
        assert r.config_name == "app-config"
        assert r.validation_type == ValidationType.SCHEMA

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_validation(
            "db-config",
            validation_type=ValidationType.SECURITY,
            result=ValidationResult.FAILED,
            scope=ConfigScope.DATABASE,
            failure_rate_pct=15.0,
            details="Missing encryption settings",
        )
        assert r.result == ValidationResult.FAILED
        assert r.scope == ConfigScope.DATABASE
        assert r.failure_rate_pct == 15.0
        assert r.details == "Missing encryption settings"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_validation(f"cfg-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_validation
# -------------------------------------------------------------------


class TestGetValidation:
    def test_found(self):
        eng = _engine()
        r = eng.record_validation("app-config")
        assert eng.get_validation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_validation("nonexistent") is None


# -------------------------------------------------------------------
# list_validations
# -------------------------------------------------------------------


class TestListValidations:
    def test_list_all(self):
        eng = _engine()
        eng.record_validation("cfg-a")
        eng.record_validation("cfg-b")
        assert len(eng.list_validations()) == 2

    def test_filter_by_config_name(self):
        eng = _engine()
        eng.record_validation("cfg-a")
        eng.record_validation("cfg-b")
        results = eng.list_validations(config_name="cfg-a")
        assert len(results) == 1
        assert results[0].config_name == "cfg-a"

    def test_filter_by_validation_type(self):
        eng = _engine()
        eng.record_validation("cfg-a", validation_type=ValidationType.SCHEMA)
        eng.record_validation("cfg-b", validation_type=ValidationType.SECURITY)
        results = eng.list_validations(validation_type=ValidationType.SECURITY)
        assert len(results) == 1
        assert results[0].config_name == "cfg-b"


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        rl = eng.add_rule(
            "schema-check",
            validation_type=ValidationType.SCHEMA,
            result=ValidationResult.PASSED,
            scope=ConfigScope.APPLICATION,
            max_allowed_failures=5,
        )
        assert rl.rule_name == "schema-check"
        assert rl.validation_type == ValidationType.SCHEMA
        assert rl.max_allowed_failures == 5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._rules) == 2


# -------------------------------------------------------------------
# analyze_validation_health
# -------------------------------------------------------------------


class TestAnalyzeValidationHealth:
    def test_with_data(self):
        eng = _engine(max_failure_rate_pct=5.0)
        eng.record_validation("cfg-a", result=ValidationResult.PASSED, failure_rate_pct=1.0)
        eng.record_validation("cfg-a", result=ValidationResult.PASSED, failure_rate_pct=2.0)
        eng.record_validation("cfg-a", result=ValidationResult.FAILED, failure_rate_pct=10.0)
        result = eng.analyze_validation_health("cfg-a")
        assert result["pass_rate"] == 66.67
        assert result["record_count"] == 3

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_validation_health("unknown-cfg")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(max_failure_rate_pct=5.0)
        eng.record_validation("cfg-a", result=ValidationResult.PASSED)
        eng.record_validation("cfg-a", result=ValidationResult.PASSED)
        result = eng.analyze_validation_health("cfg-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_failing_configs
# -------------------------------------------------------------------


class TestIdentifyFailingConfigs:
    def test_with_failures(self):
        eng = _engine()
        eng.record_validation("cfg-a", result=ValidationResult.FAILED)
        eng.record_validation("cfg-a", result=ValidationResult.ERROR)
        eng.record_validation("cfg-b", result=ValidationResult.PASSED)
        results = eng.identify_failing_configs()
        assert len(results) == 1
        assert results[0]["config_name"] == "cfg-a"
        assert results[0]["failure_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_failing_configs() == []

    def test_single_failure_not_returned(self):
        eng = _engine()
        eng.record_validation("cfg-a", result=ValidationResult.FAILED)
        assert eng.identify_failing_configs() == []


# -------------------------------------------------------------------
# rank_by_failure_rate
# -------------------------------------------------------------------


class TestRankByFailureRate:
    def test_with_data(self):
        eng = _engine()
        eng.record_validation("cfg-a", failure_rate_pct=2.0)
        eng.record_validation("cfg-b", failure_rate_pct=15.0)
        results = eng.rank_by_failure_rate()
        assert results[0]["config_name"] == "cfg-b"
        assert results[0]["avg_failure_rate_pct"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_failure_rate() == []


# -------------------------------------------------------------------
# detect_validation_trends
# -------------------------------------------------------------------


class TestDetectValidationTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_validation("cfg-a")
        eng.record_validation("cfg-b")
        results = eng.detect_validation_trends()
        assert len(results) == 1
        assert results[0]["config_name"] == "cfg-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_validation_trends() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_validation("cfg-a")
        assert eng.detect_validation_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_validation("cfg-a", result=ValidationResult.FAILED)
        eng.record_validation("cfg-b", result=ValidationResult.PASSED)
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_validations == 2
        assert report.total_rules == 1
        assert report.by_type != {}
        assert report.by_result != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_validations == 0
        assert report.pass_rate_pct == 0.0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_validation("cfg-a")
        eng.add_rule("rule-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_validations"] == 0
        assert stats["total_rules"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine(max_failure_rate_pct=5.0)
        eng.record_validation("cfg-a", validation_type=ValidationType.SCHEMA)
        eng.record_validation("cfg-b", validation_type=ValidationType.SECURITY)
        eng.add_rule("rule-1")
        stats = eng.get_stats()
        assert stats["total_validations"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_configs"] == 2
        assert stats["max_failure_rate_pct"] == 5.0
