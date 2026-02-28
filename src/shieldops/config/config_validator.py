"""Config Validation Engine — validate configuration across environments."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ValidationType(StrEnum):
    SCHEMA = "schema"
    CONSISTENCY = "consistency"
    DEPENDENCY = "dependency"
    SECURITY = "security"
    PERFORMANCE = "performance"


class ValidationResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"


class ConfigScope(StrEnum):
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"
    NETWORK = "network"
    DATABASE = "database"
    SECURITY = "security"


# --- Models ---


class ValidationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    config_name: str = ""
    validation_type: ValidationType = ValidationType.SCHEMA
    result: ValidationResult = ValidationResult.PASSED
    scope: ConfigScope = ConfigScope.APPLICATION
    failure_rate_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ValidationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    validation_type: ValidationType = ValidationType.SCHEMA
    result: ValidationResult = ValidationResult.PASSED
    scope: ConfigScope = ConfigScope.APPLICATION
    max_allowed_failures: int = 3
    created_at: float = Field(default_factory=time.time)


class ConfigValidationReport(BaseModel):
    total_validations: int = 0
    total_rules: int = 0
    pass_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    failure_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ConfigValidationEngine:
    """Validate configuration across environments."""

    def __init__(
        self,
        max_records: int = 200000,
        max_failure_rate_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_failure_rate_pct = max_failure_rate_pct
        self._records: list[ValidationRecord] = []
        self._rules: list[ValidationRule] = []
        logger.info(
            "config_validator.initialized",
            max_records=max_records,
            max_failure_rate_pct=max_failure_rate_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_validation(
        self,
        config_name: str,
        validation_type: ValidationType = ValidationType.SCHEMA,
        result: ValidationResult = ValidationResult.PASSED,
        scope: ConfigScope = ConfigScope.APPLICATION,
        failure_rate_pct: float = 0.0,
        details: str = "",
    ) -> ValidationRecord:
        record = ValidationRecord(
            config_name=config_name,
            validation_type=validation_type,
            result=result,
            scope=scope,
            failure_rate_pct=failure_rate_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "config_validator.validation_recorded",
            record_id=record.id,
            config_name=config_name,
            validation_type=validation_type.value,
            result=result.value,
        )
        return record

    def get_validation(self, record_id: str) -> ValidationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_validations(
        self,
        config_name: str | None = None,
        validation_type: ValidationType | None = None,
        limit: int = 50,
    ) -> list[ValidationRecord]:
        results = list(self._records)
        if config_name is not None:
            results = [r for r in results if r.config_name == config_name]
        if validation_type is not None:
            results = [r for r in results if r.validation_type == validation_type]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        validation_type: ValidationType = ValidationType.SCHEMA,
        result: ValidationResult = ValidationResult.PASSED,
        scope: ConfigScope = ConfigScope.APPLICATION,
        max_allowed_failures: int = 3,
    ) -> ValidationRule:
        rule = ValidationRule(
            rule_name=rule_name,
            validation_type=validation_type,
            result=result,
            scope=scope,
            max_allowed_failures=max_allowed_failures,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "config_validator.rule_added",
            rule_name=rule_name,
            validation_type=validation_type.value,
            scope=scope.value,
        )
        return rule

    # -- domain operations -----------------------------------------------

    def analyze_validation_health(self, config_name: str) -> dict[str, Any]:
        """Analyze validation health for a specific config."""
        records = [r for r in self._records if r.config_name == config_name]
        if not records:
            return {"config_name": config_name, "status": "no_data"}
        passed = sum(1 for r in records if r.result == ValidationResult.PASSED)
        pass_rate = round(passed / len(records) * 100, 2)
        return {
            "config_name": config_name,
            "pass_rate": pass_rate,
            "record_count": len(records),
            "meets_threshold": pass_rate >= (100.0 - self._max_failure_rate_pct),
        }

    def identify_failing_configs(self) -> list[dict[str, Any]]:
        """Find configs with >1 FAILED or ERROR result."""
        failure_counts: dict[str, int] = {}
        for r in self._records:
            if r.result in (ValidationResult.FAILED, ValidationResult.ERROR):
                failure_counts[r.config_name] = failure_counts.get(r.config_name, 0) + 1
        results: list[dict[str, Any]] = []
        for cfg, count in failure_counts.items():
            if count > 1:
                results.append(
                    {
                        "config_name": cfg,
                        "failure_count": count,
                    }
                )
        results.sort(key=lambda x: x["failure_count"], reverse=True)
        return results

    def rank_by_failure_rate(self) -> list[dict[str, Any]]:
        """Rank configs by avg failure_rate_pct descending."""
        rates: dict[str, list[float]] = {}
        for r in self._records:
            rates.setdefault(r.config_name, []).append(r.failure_rate_pct)
        results: list[dict[str, Any]] = []
        for cfg, rt in rates.items():
            avg = round(sum(rt) / len(rt), 2)
            results.append(
                {
                    "config_name": cfg,
                    "avg_failure_rate_pct": avg,
                }
            )
        results.sort(key=lambda x: x["avg_failure_rate_pct"], reverse=True)
        return results

    def detect_validation_trends(self) -> list[dict[str, Any]]:
        """Detect configs with >3 records."""
        counts: dict[str, int] = {}
        for r in self._records:
            counts[r.config_name] = counts.get(r.config_name, 0) + 1
        results: list[dict[str, Any]] = []
        for cfg, count in counts.items():
            if count > 3:
                results.append(
                    {
                        "config_name": cfg,
                        "record_count": count,
                        "trend_detected": True,
                    }
                )
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ConfigValidationReport:
        by_type: dict[str, int] = {}
        by_result: dict[str, int] = {}
        for r in self._records:
            by_type[r.validation_type.value] = by_type.get(r.validation_type.value, 0) + 1
            by_result[r.result.value] = by_result.get(r.result.value, 0) + 1
        passed_count = sum(1 for r in self._records if r.result == ValidationResult.PASSED)
        pass_rate = round(passed_count / len(self._records) * 100, 2) if self._records else 0.0
        failure_count = len(self.identify_failing_configs())
        recs: list[str] = []
        if self._records and pass_rate < (100.0 - self._max_failure_rate_pct):
            recs.append(
                f"Pass rate {pass_rate}% is below {100.0 - self._max_failure_rate_pct}% threshold"
            )
        if failure_count > 0:
            recs.append(f"{failure_count} config(s) with failures")
        trends = len(self.detect_validation_trends())
        if trends > 0:
            recs.append(f"{trends} config(s) with detected trends")
        if not recs:
            recs.append("Configuration validation meets targets")
        return ConfigValidationReport(
            total_validations=len(self._records),
            total_rules=len(self._rules),
            pass_rate_pct=pass_rate,
            by_type=by_type,
            by_result=by_result,
            failure_count=failure_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("config_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.validation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_validations": len(self._records),
            "total_rules": len(self._rules),
            "max_failure_rate_pct": self._max_failure_rate_pct,
            "type_distribution": type_dist,
            "unique_configs": len({r.config_name for r in self._records}),
        }
