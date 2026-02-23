"""Startup configuration validator.

Validates required secrets and configuration at application startup,
providing clear error messages instead of cryptic runtime failures.
"""

from __future__ import annotations

import os
import re
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class SecretCategory(StrEnum):
    DATABASE = "database"
    CACHE = "cache"
    LLM = "llm"
    OBSERVABILITY = "observability"
    AUTH = "auth"
    MESSAGING = "messaging"
    POLICY = "policy"


class ValidationIssue(BaseModel):
    """A single validation issue found during startup check."""

    category: SecretCategory
    key: str
    message: str
    severity: str = "error"  # "error" or "warning"


class ValidationResult(BaseModel):
    """Result of startup validation."""

    valid: bool = True
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    checked_count: int = 0


# URL pattern for basic format validation
_URL_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://")


class StartupValidator:
    """Validates all required secrets and config at application startup.

    Usage::

        validator = StartupValidator()
        result = validator.validate()
        if not result.valid:
            for err in result.errors:
                print(f"FATAL: [{err.category}] {err.key}: {err.message}")
    """

    # Required env vars by category with validation rules
    REQUIRED_CHECKS: list[dict[str, Any]] = [
        {
            "category": SecretCategory.DATABASE,
            "key": "SHIELDOPS_DATABASE_URL",
            "description": "PostgreSQL connection string",
            "format": "url",
        },
        {
            "category": SecretCategory.CACHE,
            "key": "SHIELDOPS_REDIS_URL",
            "description": "Redis connection string",
            "format": "url",
        },
        {
            "category": SecretCategory.AUTH,
            "key": "SHIELDOPS_JWT_SECRET_KEY",
            "description": "JWT signing secret",
            "min_length": 16,
        },
    ]

    OPTIONAL_CHECKS: list[dict[str, Any]] = [
        {
            "category": SecretCategory.LLM,
            "key": "SHIELDOPS_ANTHROPIC_API_KEY",
            "description": "Anthropic API key",
        },
        {
            "category": SecretCategory.LLM,
            "key": "SHIELDOPS_OPENAI_API_KEY",
            "description": "OpenAI API key",
        },
        {
            "category": SecretCategory.POLICY,
            "key": "SHIELDOPS_OPA_ENDPOINT",
            "description": "OPA policy engine URL",
            "format": "url",
        },
        {
            "category": SecretCategory.OBSERVABILITY,
            "key": "SHIELDOPS_LANGSMITH_API_KEY",
            "description": "LangSmith tracing API key",
        },
        {
            "category": SecretCategory.MESSAGING,
            "key": "SHIELDOPS_KAFKA_BROKERS",
            "description": "Kafka broker list",
        },
    ]

    def __init__(
        self,
        env: dict[str, str] | None = None,
        check_connectivity: bool = False,
    ) -> None:
        self._env = env if env is not None else dict(os.environ)
        self._check_connectivity = check_connectivity

    def validate(self) -> ValidationResult:
        """Run all validation checks and return the result."""
        result = ValidationResult()

        # Required checks
        for check in self.REQUIRED_CHECKS:
            result.checked_count += 1
            self._validate_check(check, result, required=True)

        # Optional checks (produce warnings)
        for check in self.OPTIONAL_CHECKS:
            result.checked_count += 1
            self._validate_check(check, result, required=False)

        result.valid = len(result.errors) == 0
        return result

    def _validate_check(
        self,
        check: dict[str, Any],
        result: ValidationResult,
        required: bool,
    ) -> None:
        key = check["key"]
        category = check["category"]
        value = self._env.get(key, "")

        # Presence check
        if not value:
            issue = ValidationIssue(
                category=category,
                key=key,
                message=f"{check['description']} is not set",
                severity="error" if required else "warning",
            )
            if required:
                result.errors.append(issue)
            else:
                result.warnings.append(issue)
            return

        # Format check (URL)
        fmt = check.get("format")
        if fmt == "url" and not _URL_PATTERN.match(value):
            issue = ValidationIssue(
                category=category,
                key=key,
                message=f"{check['description']} has invalid URL format: {value[:30]}...",
                severity="error" if required else "warning",
            )
            if required:
                result.errors.append(issue)
            else:
                result.warnings.append(issue)
            return

        # Minimum length
        min_len = check.get("min_length")
        if min_len and len(value) < min_len:
            issue = ValidationIssue(
                category=category,
                key=key,
                message=(
                    f"{check['description']} is too short (min {min_len} chars, got {len(value)})"
                ),
                severity="error" if required else "warning",
            )
            if required:
                result.errors.append(issue)
            else:
                result.warnings.append(issue)

    async def validate_connectivity(self) -> ValidationResult:
        """Extended validation that also checks external service connectivity."""
        result = self.validate()

        if not self._check_connectivity:
            return result

        # Database ping
        db_url = self._env.get("SHIELDOPS_DATABASE_URL", "")
        if db_url:
            try:
                from sqlalchemy import text

                from shieldops.db.session import create_async_engine

                engine = create_async_engine(db_url, pool_size=1)
                async with engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
                await engine.dispose()
            except Exception as e:
                result.errors.append(
                    ValidationIssue(
                        category=SecretCategory.DATABASE,
                        key="SHIELDOPS_DATABASE_URL",
                        message=f"Database connectivity check failed: {e}",
                        severity="error",
                    )
                )
                result.valid = False

        # Redis ping
        redis_url = self._env.get("SHIELDOPS_REDIS_URL", "")
        if redis_url:
            try:
                import redis.asyncio as aioredis

                r = aioredis.from_url(redis_url, socket_connect_timeout=2)  # type: ignore[no-untyped-call]
                await r.ping()  # type: ignore[misc]
                await r.aclose()
            except Exception as e:
                result.warnings.append(
                    ValidationIssue(
                        category=SecretCategory.CACHE,
                        key="SHIELDOPS_REDIS_URL",
                        message=f"Redis connectivity check failed: {e}",
                        severity="warning",
                    )
                )

        return result
