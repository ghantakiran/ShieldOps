"""Tests for shieldops.config.parity_validator — ConfigurationParityValidator."""

from __future__ import annotations

from shieldops.config.parity_validator import (
    ConfigurationParityValidator,
    EnvironmentConfig,
    EnvironmentRole,
    ParityLevel,
    ParityReport,
    ParityViolation,
    ParityViolationType,
)


def _engine(**kw) -> ConfigurationParityValidator:
    return ConfigurationParityValidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_violation_missing_key(self):
        assert ParityViolationType.MISSING_KEY == "missing_key"

    def test_violation_value_divergence(self):
        assert ParityViolationType.VALUE_DIVERGENCE == "value_divergence"

    def test_violation_type_mismatch(self):
        assert ParityViolationType.TYPE_MISMATCH == "type_mismatch"

    def test_violation_extra_key(self):
        assert ParityViolationType.EXTRA_KEY == "extra_key"

    def test_role_development(self):
        assert EnvironmentRole.DEVELOPMENT == "development"

    def test_role_staging(self):
        assert EnvironmentRole.STAGING == "staging"

    def test_role_production(self):
        assert EnvironmentRole.PRODUCTION == "production"

    def test_role_dr(self):
        assert EnvironmentRole.DR == "dr"

    def test_level_identical(self):
        assert ParityLevel.IDENTICAL == "identical"

    def test_level_compatible(self):
        assert ParityLevel.COMPATIBLE == "compatible"

    def test_level_divergent(self):
        assert ParityLevel.DIVERGENT == "divergent"

    def test_level_critical(self):
        assert ParityLevel.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_env_config_defaults(self):
        config = EnvironmentConfig(environment="dev")
        assert config.id
        assert config.environment == "dev"
        assert config.role == EnvironmentRole.DEVELOPMENT
        assert config.config_data == {}

    def test_violation_defaults(self):
        v = ParityViolation(
            env_a="dev",
            env_b="prod",
            key="DB_HOST",
            violation_type=ParityViolationType.MISSING_KEY,
        )
        assert v.id
        assert v.value_a == ""

    def test_report_defaults(self):
        r = ParityReport(env_a="dev", env_b="prod")
        assert r.parity_level == ParityLevel.IDENTICAL
        assert r.score == 100.0
        assert r.violation_count == 0


# ---------------------------------------------------------------------------
# capture_config
# ---------------------------------------------------------------------------


class TestCaptureConfig:
    def test_basic_capture(self):
        eng = _engine()
        config = eng.capture_config("dev", config_data={"DB_HOST": "localhost"})
        assert config.environment == "dev"
        assert eng.get_config(config.id) is not None

    def test_unique_ids(self):
        eng = _engine()
        c1 = eng.capture_config("dev")
        c2 = eng.capture_config("staging")
        assert c1.id != c2.id

    def test_evicts_at_max(self):
        eng = _engine(max_configs=2)
        c1 = eng.capture_config("env-1")
        eng.capture_config("env-2")
        eng.capture_config("env-3")
        assert eng.get_config(c1.id) is None


# ---------------------------------------------------------------------------
# get_config / list_configs / delete_config
# ---------------------------------------------------------------------------


class TestGetConfig:
    def test_found(self):
        eng = _engine()
        config = eng.capture_config("dev")
        assert eng.get_config(config.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_config("nonexistent") is None


class TestListConfigs:
    def test_list_all(self):
        eng = _engine()
        eng.capture_config("dev")
        eng.capture_config("staging")
        assert len(eng.list_configs()) == 2

    def test_filter_by_environment(self):
        eng = _engine()
        eng.capture_config("dev")
        eng.capture_config("staging")
        results = eng.list_configs(environment="dev")
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.capture_config("dev", service="auth")
        eng.capture_config("dev", service="billing")
        results = eng.list_configs(service="auth")
        assert len(results) == 1


class TestDeleteConfig:
    def test_delete(self):
        eng = _engine()
        config = eng.capture_config("dev")
        assert eng.delete_config(config.id) is True
        assert eng.get_config(config.id) is None

    def test_delete_not_found(self):
        eng = _engine()
        assert eng.delete_config("nonexistent") is False


# ---------------------------------------------------------------------------
# compare_environments
# ---------------------------------------------------------------------------


class TestCompareEnvironments:
    def test_identical(self):
        eng = _engine()
        eng.capture_config("dev", config_data={"DB_HOST": "localhost", "PORT": "5432"})
        eng.capture_config("staging", config_data={"DB_HOST": "localhost", "PORT": "5432"})
        report = eng.compare_environments("dev", "staging")
        assert report.parity_level == ParityLevel.IDENTICAL
        assert report.score == 100.0

    def test_missing_key(self):
        eng = _engine()
        eng.capture_config("dev", config_data={"DB_HOST": "localhost", "PORT": "5432"})
        eng.capture_config("staging", config_data={"DB_HOST": "localhost"})
        report = eng.compare_environments("dev", "staging")
        assert report.violation_count == 1
        assert report.violations[0].violation_type == ParityViolationType.MISSING_KEY

    def test_value_divergence(self):
        eng = _engine()
        eng.capture_config("dev", config_data={"DB_HOST": "localhost"})
        eng.capture_config("staging", config_data={"DB_HOST": "db.staging.local"})
        report = eng.compare_environments("dev", "staging")
        assert report.violation_count == 1
        assert report.violations[0].violation_type == ParityViolationType.VALUE_DIVERGENCE

    def test_type_mismatch(self):
        eng = _engine()
        eng.capture_config("dev", config_data={"PORT": 5432})
        eng.capture_config("staging", config_data={"PORT": "5432"})
        report = eng.compare_environments("dev", "staging")
        assert report.violations[0].violation_type == ParityViolationType.TYPE_MISMATCH

    def test_no_configs(self):
        eng = _engine()
        report = eng.compare_environments("dev", "staging")
        assert report.parity_level == ParityLevel.IDENTICAL
        assert report.violation_count == 0


# ---------------------------------------------------------------------------
# compare_all_environments
# ---------------------------------------------------------------------------


class TestCompareAll:
    def test_basic_compare_all(self):
        eng = _engine()
        eng.capture_config("dev", config_data={"KEY": "val"})
        eng.capture_config("staging", config_data={"KEY": "val"})
        eng.capture_config("prod", config_data={"KEY": "val"})
        reports = eng.compare_all_environments()
        assert len(reports) == 3  # dev-staging, dev-prod, staging-prod


# ---------------------------------------------------------------------------
# list_violations / parity_score / critical / stats
# ---------------------------------------------------------------------------


class TestListViolations:
    def test_filter_by_env(self):
        eng = _engine()
        eng.capture_config("dev", config_data={"A": "1", "B": "2"})
        eng.capture_config("staging", config_data={"A": "1"})
        eng.compare_environments("dev", "staging")
        results = eng.list_violations(env_a="dev")
        assert len(results) >= 1


class TestParityScore:
    def test_score(self):
        eng = _engine()
        eng.capture_config("dev", config_data={"KEY": "val"})
        eng.capture_config("staging", config_data={"KEY": "val"})
        score = eng.get_parity_score("dev", "staging")
        assert score == 100.0


class TestCriticalDivergences:
    def test_critical(self):
        eng = _engine()
        eng.capture_config("dev", config_data={"A": "1", "B": "2"})
        eng.capture_config("staging", config_data={"A": "1"})
        eng.compare_environments("dev", "staging")
        critical = eng.get_critical_divergences()
        assert len(critical) >= 1


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_configs"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.capture_config("dev")
        eng.capture_config("staging")
        stats = eng.get_stats()
        assert stats["total_configs"] == 2
