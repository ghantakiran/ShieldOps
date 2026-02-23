"""Tests for shieldops.config.startup_validator module.

Covers SecretCategory enum, ValidationIssue model, ValidationResult model,
StartupValidator with required and optional checks, URL format validation,
minimum length validation, and connectivity validation.
"""

from __future__ import annotations

import pytest

from shieldops.config.startup_validator import (
    SecretCategory,
    StartupValidator,
    ValidationIssue,
    ValidationResult,
)

# ---------------------------------------------------------------------------
# SecretCategory enum
# ---------------------------------------------------------------------------


class TestSecretCategory:
    """Tests for the SecretCategory StrEnum."""

    def test_database_value(self) -> None:
        assert SecretCategory.DATABASE == "database"

    def test_cache_value(self) -> None:
        assert SecretCategory.CACHE == "cache"

    def test_llm_value(self) -> None:
        assert SecretCategory.LLM == "llm"

    def test_observability_value(self) -> None:
        assert SecretCategory.OBSERVABILITY == "observability"

    def test_auth_value(self) -> None:
        assert SecretCategory.AUTH == "auth"

    def test_messaging_value(self) -> None:
        assert SecretCategory.MESSAGING == "messaging"

    def test_policy_value(self) -> None:
        assert SecretCategory.POLICY == "policy"

    def test_all_members(self) -> None:
        expected = {"database", "cache", "llm", "observability", "auth", "messaging", "policy"}
        assert set(SecretCategory) == expected

    def test_is_str_subclass(self) -> None:
        assert isinstance(SecretCategory.DATABASE, str)

    def test_member_count(self) -> None:
        assert len(SecretCategory) == 7


# ---------------------------------------------------------------------------
# ValidationIssue model
# ---------------------------------------------------------------------------


class TestValidationIssue:
    """Tests for the ValidationIssue Pydantic model."""

    def test_construction(self) -> None:
        issue = ValidationIssue(
            category=SecretCategory.DATABASE,
            key="SHIELDOPS_DATABASE_URL",
            message="PostgreSQL connection string is not set",
        )
        assert issue.category == SecretCategory.DATABASE
        assert issue.key == "SHIELDOPS_DATABASE_URL"
        assert issue.message == "PostgreSQL connection string is not set"

    def test_default_severity_is_error(self) -> None:
        issue = ValidationIssue(
            category=SecretCategory.DATABASE,
            key="X",
            message="missing",
        )
        assert issue.severity == "error"

    def test_custom_severity(self) -> None:
        issue = ValidationIssue(
            category=SecretCategory.LLM,
            key="X",
            message="missing",
            severity="warning",
        )
        assert issue.severity == "warning"

    def test_serialization(self) -> None:
        issue = ValidationIssue(
            category=SecretCategory.AUTH,
            key="SHIELDOPS_JWT_SECRET_KEY",
            message="too short",
            severity="error",
        )
        data = issue.model_dump()
        assert data["category"] == "auth"
        assert data["key"] == "SHIELDOPS_JWT_SECRET_KEY"
        assert data["severity"] == "error"


# ---------------------------------------------------------------------------
# ValidationResult model
# ---------------------------------------------------------------------------


class TestValidationResult:
    """Tests for the ValidationResult Pydantic model."""

    def test_defaults(self) -> None:
        result = ValidationResult()
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.checked_count == 0

    def test_with_errors(self) -> None:
        issue = ValidationIssue(
            category=SecretCategory.DATABASE,
            key="X",
            message="missing",
        )
        result = ValidationResult(valid=False, errors=[issue], checked_count=1)
        assert result.valid is False
        assert len(result.errors) == 1

    def test_with_warnings(self) -> None:
        issue = ValidationIssue(
            category=SecretCategory.LLM,
            key="X",
            message="missing",
            severity="warning",
        )
        result = ValidationResult(valid=True, warnings=[issue], checked_count=1)
        assert result.valid is True
        assert len(result.warnings) == 1


# ---------------------------------------------------------------------------
# StartupValidator — valid configuration
# ---------------------------------------------------------------------------


def _valid_env() -> dict[str, str]:
    """Return a minimal valid environment for all required checks."""
    return {
        "SHIELDOPS_DATABASE_URL": "postgresql://user:pass@localhost:5432/shieldops",
        "SHIELDOPS_REDIS_URL": "redis://localhost:6379/0",
        "SHIELDOPS_JWT_SECRET_KEY": "a-very-secure-secret-key-at-least-16",
    }


class TestStartupValidatorValid:
    """Tests for a fully valid configuration."""

    def test_valid_config_passes(self) -> None:
        validator = StartupValidator(env=_valid_env())
        result = validator.validate()
        assert result.valid is True
        assert len(result.errors) == 0

    def test_checked_count_includes_all_checks(self) -> None:
        validator = StartupValidator(env=_valid_env())
        result = validator.validate()
        expected = len(StartupValidator.REQUIRED_CHECKS) + len(StartupValidator.OPTIONAL_CHECKS)
        assert result.checked_count == expected

    def test_valid_config_may_have_warnings_for_optional(self) -> None:
        """A valid config (no errors) can still have warnings for missing optional vars."""
        validator = StartupValidator(env=_valid_env())
        result = validator.validate()
        # Optional keys are not set, so there should be warnings
        assert len(result.warnings) > 0

    def test_valid_config_with_all_optional_vars(self) -> None:
        env = _valid_env()
        env.update(
            {
                "SHIELDOPS_ANTHROPIC_API_KEY": "sk-ant-test-key",
                "SHIELDOPS_OPENAI_API_KEY": "sk-test-key",
                "SHIELDOPS_OPA_ENDPOINT": "http://localhost:8181/v1",
                "SHIELDOPS_LANGSMITH_API_KEY": "ls-test-key",
                "SHIELDOPS_KAFKA_BROKERS": "localhost:9092",
            }
        )
        validator = StartupValidator(env=env)
        result = validator.validate()
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0


# ---------------------------------------------------------------------------
# StartupValidator — missing required env vars
# ---------------------------------------------------------------------------


class TestStartupValidatorMissingRequired:
    """Tests for missing required environment variables."""

    def test_missing_database_url(self) -> None:
        env = _valid_env()
        del env["SHIELDOPS_DATABASE_URL"]
        validator = StartupValidator(env=env)
        result = validator.validate()
        assert result.valid is False
        error_keys = [e.key for e in result.errors]
        assert "SHIELDOPS_DATABASE_URL" in error_keys

    def test_missing_redis_url(self) -> None:
        env = _valid_env()
        del env["SHIELDOPS_REDIS_URL"]
        validator = StartupValidator(env=env)
        result = validator.validate()
        assert result.valid is False
        error_keys = [e.key for e in result.errors]
        assert "SHIELDOPS_REDIS_URL" in error_keys

    def test_missing_jwt_secret(self) -> None:
        env = _valid_env()
        del env["SHIELDOPS_JWT_SECRET_KEY"]
        validator = StartupValidator(env=env)
        result = validator.validate()
        assert result.valid is False
        error_keys = [e.key for e in result.errors]
        assert "SHIELDOPS_JWT_SECRET_KEY" in error_keys

    def test_missing_all_required(self) -> None:
        validator = StartupValidator(env={})
        result = validator.validate()
        assert result.valid is False
        assert len(result.errors) == len(StartupValidator.REQUIRED_CHECKS)

    def test_empty_string_treated_as_missing(self) -> None:
        env = _valid_env()
        env["SHIELDOPS_DATABASE_URL"] = ""
        validator = StartupValidator(env=env)
        result = validator.validate()
        assert result.valid is False
        error_keys = [e.key for e in result.errors]
        assert "SHIELDOPS_DATABASE_URL" in error_keys

    def test_error_severity_is_error(self) -> None:
        validator = StartupValidator(env={})
        result = validator.validate()
        for error in result.errors:
            assert error.severity == "error"

    def test_error_message_includes_description(self) -> None:
        validator = StartupValidator(env={})
        result = validator.validate()
        db_errors = [e for e in result.errors if e.key == "SHIELDOPS_DATABASE_URL"]
        assert len(db_errors) == 1
        assert "PostgreSQL connection string" in db_errors[0].message

    def test_error_category_matches(self) -> None:
        validator = StartupValidator(env={})
        result = validator.validate()
        db_errors = [e for e in result.errors if e.key == "SHIELDOPS_DATABASE_URL"]
        assert db_errors[0].category == SecretCategory.DATABASE


# ---------------------------------------------------------------------------
# StartupValidator — invalid URL format
# ---------------------------------------------------------------------------


class TestStartupValidatorURLFormat:
    """Tests for URL format validation."""

    def test_invalid_database_url_format(self) -> None:
        env = _valid_env()
        env["SHIELDOPS_DATABASE_URL"] = "not-a-url"
        validator = StartupValidator(env=env)
        result = validator.validate()
        assert result.valid is False
        error_keys = [e.key for e in result.errors]
        assert "SHIELDOPS_DATABASE_URL" in error_keys

    def test_invalid_redis_url_format(self) -> None:
        env = _valid_env()
        env["SHIELDOPS_REDIS_URL"] = "just-a-hostname"
        validator = StartupValidator(env=env)
        result = validator.validate()
        assert result.valid is False
        error_keys = [e.key for e in result.errors]
        assert "SHIELDOPS_REDIS_URL" in error_keys

    def test_valid_url_formats(self) -> None:
        """Various valid URL schemes should pass validation."""
        env = _valid_env()
        env["SHIELDOPS_DATABASE_URL"] = "postgresql+asyncpg://user:pass@host:5432/db"
        env["SHIELDOPS_REDIS_URL"] = "rediss://secure-host:6380/0"
        validator = StartupValidator(env=env)
        result = validator.validate()
        url_errors = [
            e for e in result.errors if e.key in ("SHIELDOPS_DATABASE_URL", "SHIELDOPS_REDIS_URL")
        ]
        assert len(url_errors) == 0

    def test_url_error_message_mentions_format(self) -> None:
        env = _valid_env()
        env["SHIELDOPS_DATABASE_URL"] = "bad-url"
        validator = StartupValidator(env=env)
        result = validator.validate()
        db_errors = [e for e in result.errors if e.key == "SHIELDOPS_DATABASE_URL"]
        assert "invalid URL format" in db_errors[0].message

    def test_optional_url_format_check(self) -> None:
        """Optional vars with URL format check should produce warnings, not errors."""
        env = _valid_env()
        env["SHIELDOPS_OPA_ENDPOINT"] = "not-a-url"
        validator = StartupValidator(env=env)
        result = validator.validate()
        # It should be valid (no errors from this) but have a warning
        opa_warnings = [w for w in result.warnings if w.key == "SHIELDOPS_OPA_ENDPOINT"]
        assert len(opa_warnings) == 1
        assert "invalid URL format" in opa_warnings[0].message


# ---------------------------------------------------------------------------
# StartupValidator — JWT secret minimum length
# ---------------------------------------------------------------------------


class TestStartupValidatorJWTLength:
    """Tests for JWT secret minimum length validation."""

    def test_jwt_secret_too_short(self) -> None:
        env = _valid_env()
        env["SHIELDOPS_JWT_SECRET_KEY"] = "short"  # noqa: S105
        validator = StartupValidator(env=env)
        result = validator.validate()
        assert result.valid is False
        jwt_errors = [e for e in result.errors if e.key == "SHIELDOPS_JWT_SECRET_KEY"]
        assert len(jwt_errors) == 1

    def test_jwt_secret_exactly_min_length(self) -> None:
        env = _valid_env()
        env["SHIELDOPS_JWT_SECRET_KEY"] = "a" * 16  # Exactly 16 chars
        validator = StartupValidator(env=env)
        result = validator.validate()
        jwt_errors = [e for e in result.errors if e.key == "SHIELDOPS_JWT_SECRET_KEY"]
        assert len(jwt_errors) == 0

    def test_jwt_error_message_mentions_length(self) -> None:
        env = _valid_env()
        env["SHIELDOPS_JWT_SECRET_KEY"] = "abc"  # noqa: S105
        validator = StartupValidator(env=env)
        result = validator.validate()
        jwt_errors = [e for e in result.errors if e.key == "SHIELDOPS_JWT_SECRET_KEY"]
        assert "too short" in jwt_errors[0].message
        assert "min 16" in jwt_errors[0].message

    def test_jwt_secret_one_char(self) -> None:
        env = _valid_env()
        env["SHIELDOPS_JWT_SECRET_KEY"] = "x"  # noqa: S105
        validator = StartupValidator(env=env)
        result = validator.validate()
        jwt_errors = [e for e in result.errors if e.key == "SHIELDOPS_JWT_SECRET_KEY"]
        assert len(jwt_errors) == 1
        assert "got 1" in jwt_errors[0].message


# ---------------------------------------------------------------------------
# StartupValidator — optional missing vars are warnings
# ---------------------------------------------------------------------------


class TestStartupValidatorOptional:
    """Tests for optional environment variable handling."""

    def test_missing_optional_produces_warning(self) -> None:
        validator = StartupValidator(env=_valid_env())
        result = validator.validate()
        warning_keys = {w.key for w in result.warnings}
        assert "SHIELDOPS_ANTHROPIC_API_KEY" in warning_keys
        assert "SHIELDOPS_OPENAI_API_KEY" in warning_keys

    def test_optional_missing_does_not_fail_validation(self) -> None:
        validator = StartupValidator(env=_valid_env())
        result = validator.validate()
        assert result.valid is True

    def test_warning_severity_is_warning(self) -> None:
        validator = StartupValidator(env=_valid_env())
        result = validator.validate()
        for warning in result.warnings:
            assert warning.severity == "warning"

    def test_optional_present_produces_no_warning(self) -> None:
        env = _valid_env()
        env["SHIELDOPS_ANTHROPIC_API_KEY"] = "sk-ant-valid-key"
        validator = StartupValidator(env=env)
        result = validator.validate()
        anthropic_warnings = [w for w in result.warnings if w.key == "SHIELDOPS_ANTHROPIC_API_KEY"]
        assert len(anthropic_warnings) == 0

    def test_all_optional_present_no_warnings(self) -> None:
        env = _valid_env()
        env.update(
            {
                "SHIELDOPS_ANTHROPIC_API_KEY": "sk-ant-test-key",
                "SHIELDOPS_OPENAI_API_KEY": "sk-test-key",
                "SHIELDOPS_OPA_ENDPOINT": "http://localhost:8181/v1",
                "SHIELDOPS_LANGSMITH_API_KEY": "ls-test-key",
                "SHIELDOPS_KAFKA_BROKERS": "localhost:9092",
            }
        )
        validator = StartupValidator(env=env)
        result = validator.validate()
        assert len(result.warnings) == 0


# ---------------------------------------------------------------------------
# StartupValidator — env injection
# ---------------------------------------------------------------------------


class TestStartupValidatorEnvInjection:
    """Tests for environment dictionary injection."""

    def test_uses_injected_env(self) -> None:
        env = {"SHIELDOPS_DATABASE_URL": "postgresql://host/db"}
        validator = StartupValidator(env=env)
        result = validator.validate()
        # Database URL is present, so no error for that key
        db_errors = [e for e in result.errors if e.key == "SHIELDOPS_DATABASE_URL"]
        assert len(db_errors) == 0

    def test_default_env_uses_os_environ(self) -> None:
        """When no env is provided, validator reads from os.environ."""
        import os
        from unittest.mock import patch

        fake_env = _valid_env()
        with patch.dict(os.environ, fake_env, clear=True):
            validator = StartupValidator()
            result = validator.validate()
            # Required vars are set, so no errors for them
            required_keys = {c["key"] for c in StartupValidator.REQUIRED_CHECKS}
            error_keys = {e.key for e in result.errors}
            assert not required_keys.intersection(error_keys)


# ---------------------------------------------------------------------------
# StartupValidator — validate() return structure
# ---------------------------------------------------------------------------


class TestStartupValidatorReturnStructure:
    """Tests for the structure and counts in ValidationResult."""

    def test_validate_returns_validation_result(self) -> None:
        validator = StartupValidator(env=_valid_env())
        result = validator.validate()
        assert isinstance(result, ValidationResult)

    def test_valid_true_when_no_errors(self) -> None:
        validator = StartupValidator(env=_valid_env())
        result = validator.validate()
        assert result.valid is True

    def test_valid_false_when_errors_present(self) -> None:
        validator = StartupValidator(env={})
        result = validator.validate()
        assert result.valid is False

    def test_checked_count_matches_total_checks(self) -> None:
        validator = StartupValidator(env=_valid_env())
        result = validator.validate()
        total = len(StartupValidator.REQUIRED_CHECKS) + len(StartupValidator.OPTIONAL_CHECKS)
        assert result.checked_count == total

    def test_error_count_plus_warning_count(self) -> None:
        """With empty env, all required produce errors, all optional produce warnings."""
        validator = StartupValidator(env={})
        result = validator.validate()
        assert len(result.errors) == len(StartupValidator.REQUIRED_CHECKS)
        assert len(result.warnings) == len(StartupValidator.OPTIONAL_CHECKS)


# ---------------------------------------------------------------------------
# StartupValidator — connectivity validation (non-connectivity mode)
# ---------------------------------------------------------------------------


class TestStartupValidatorConnectivity:
    """Tests for validate_connectivity when check_connectivity is False."""

    @pytest.mark.asyncio
    async def test_validate_connectivity_without_flag(self) -> None:
        """When check_connectivity=False, validate_connectivity returns same as validate()."""
        validator = StartupValidator(env=_valid_env(), check_connectivity=False)
        result = await validator.validate_connectivity()
        assert isinstance(result, ValidationResult)
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_validate_connectivity_checks_basic_validation(self) -> None:
        """Even without connectivity, basic validation still runs."""
        validator = StartupValidator(env={}, check_connectivity=False)
        result = await validator.validate_connectivity()
        assert result.valid is False
        assert len(result.errors) > 0
