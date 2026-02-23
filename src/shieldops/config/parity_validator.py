"""Configuration Parity Validator — cross-environment config comparison, divergence scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ParityViolationType(StrEnum):
    MISSING_KEY = "missing_key"
    VALUE_DIVERGENCE = "value_divergence"
    TYPE_MISMATCH = "type_mismatch"
    EXTRA_KEY = "extra_key"


class EnvironmentRole(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DR = "dr"


class ParityLevel(StrEnum):
    IDENTICAL = "identical"
    COMPATIBLE = "compatible"
    DIVERGENT = "divergent"
    CRITICAL = "critical"


# --- Models ---


class EnvironmentConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    environment: str
    role: EnvironmentRole = EnvironmentRole.DEVELOPMENT
    service: str = ""
    config_data: dict[str, Any] = Field(default_factory=dict)
    captured_at: float = Field(default_factory=time.time)


class ParityViolation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    env_a: str
    env_b: str
    key: str
    violation_type: ParityViolationType
    value_a: str = ""
    value_b: str = ""
    service: str = ""
    detected_at: float = Field(default_factory=time.time)


class ParityReport(BaseModel):
    env_a: str
    env_b: str
    parity_level: ParityLevel = ParityLevel.IDENTICAL
    violation_count: int = 0
    score: float = 100.0
    violations: list[ParityViolation] = Field(default_factory=list)


# --- Engine ---


class ConfigurationParityValidator:
    """Cross-environment config comparison, missing key detection, value divergence scoring."""

    def __init__(
        self,
        max_configs: int = 5000,
        max_violations: int = 50000,
    ) -> None:
        self._max_configs = max_configs
        self._max_violations = max_violations
        self._configs: dict[str, EnvironmentConfig] = {}
        self._violations: list[ParityViolation] = []
        logger.info(
            "config_parity.initialized",
            max_configs=max_configs,
            max_violations=max_violations,
        )

    def capture_config(
        self,
        environment: str,
        role: EnvironmentRole = EnvironmentRole.DEVELOPMENT,
        service: str = "",
        config_data: dict[str, Any] | None = None,
    ) -> EnvironmentConfig:
        config = EnvironmentConfig(
            environment=environment,
            role=role,
            service=service,
            config_data=config_data or {},
        )
        self._configs[config.id] = config
        if len(self._configs) > self._max_configs:
            oldest = next(iter(self._configs))
            del self._configs[oldest]
        logger.info(
            "config_parity.config_captured",
            config_id=config.id,
            environment=environment,
        )
        return config

    def get_config(self, config_id: str) -> EnvironmentConfig | None:
        return self._configs.get(config_id)

    def list_configs(
        self,
        environment: str | None = None,
        service: str | None = None,
    ) -> list[EnvironmentConfig]:
        results = list(self._configs.values())
        if environment is not None:
            results = [c for c in results if c.environment == environment]
        if service is not None:
            results = [c for c in results if c.service == service]
        return results

    def delete_config(self, config_id: str) -> bool:
        if config_id in self._configs:
            del self._configs[config_id]
            return True
        return False

    def compare_environments(
        self,
        env_a: str,
        env_b: str,
        service: str = "",
    ) -> ParityReport:
        configs_a = [
            c
            for c in self._configs.values()
            if c.environment == env_a and (not service or c.service == service)
        ]
        configs_b = [
            c
            for c in self._configs.values()
            if c.environment == env_b and (not service or c.service == service)
        ]
        if not configs_a or not configs_b:
            return ParityReport(env_a=env_a, env_b=env_b)
        data_a = configs_a[-1].config_data
        data_b = configs_b[-1].config_data
        violations: list[ParityViolation] = []
        all_keys = set(data_a.keys()) | set(data_b.keys())
        for key in sorted(all_keys):
            in_a = key in data_a
            in_b = key in data_b
            if in_a and not in_b:
                violations.append(
                    ParityViolation(
                        env_a=env_a,
                        env_b=env_b,
                        key=key,
                        violation_type=ParityViolationType.MISSING_KEY,
                        value_a=str(data_a[key]),
                        service=service,
                    )
                )
            elif in_b and not in_a:
                violations.append(
                    ParityViolation(
                        env_a=env_a,
                        env_b=env_b,
                        key=key,
                        violation_type=ParityViolationType.EXTRA_KEY,
                        value_b=str(data_b[key]),
                        service=service,
                    )
                )
            elif in_a and in_b:
                if type(data_a[key]) is not type(data_b[key]):
                    violations.append(
                        ParityViolation(
                            env_a=env_a,
                            env_b=env_b,
                            key=key,
                            violation_type=ParityViolationType.TYPE_MISMATCH,
                            value_a=str(data_a[key]),
                            value_b=str(data_b[key]),
                            service=service,
                        )
                    )
                elif data_a[key] != data_b[key]:
                    violations.append(
                        ParityViolation(
                            env_a=env_a,
                            env_b=env_b,
                            key=key,
                            violation_type=ParityViolationType.VALUE_DIVERGENCE,
                            value_a=str(data_a[key]),
                            value_b=str(data_b[key]),
                            service=service,
                        )
                    )
        self._violations.extend(violations)
        if len(self._violations) > self._max_violations:
            self._violations = self._violations[-self._max_violations :]
        total_keys = max(len(all_keys), 1)
        score = round((1 - len(violations) / total_keys) * 100, 1)
        if len(violations) == 0:
            level = ParityLevel.IDENTICAL
        elif score >= 80:
            level = ParityLevel.COMPATIBLE
        elif score >= 50:
            level = ParityLevel.DIVERGENT
        else:
            level = ParityLevel.CRITICAL
        return ParityReport(
            env_a=env_a,
            env_b=env_b,
            parity_level=level,
            violation_count=len(violations),
            score=score,
            violations=violations,
        )

    def compare_all_environments(self, service: str = "") -> list[ParityReport]:
        envs = sorted({c.environment for c in self._configs.values()})
        reports: list[ParityReport] = []
        for i, env_a in enumerate(envs):
            for env_b in envs[i + 1 :]:
                reports.append(self.compare_environments(env_a, env_b, service=service))
        return reports

    def list_violations(
        self,
        env_a: str | None = None,
        violation_type: ParityViolationType | None = None,
    ) -> list[ParityViolation]:
        results = list(self._violations)
        if env_a is not None:
            results = [v for v in results if v.env_a == env_a]
        if violation_type is not None:
            results = [v for v in results if v.violation_type == violation_type]
        return results

    def get_parity_score(self, env_a: str, env_b: str) -> float:
        report = self.compare_environments(env_a, env_b)
        return report.score

    def get_critical_divergences(self) -> list[ParityViolation]:
        return [
            v
            for v in self._violations
            if v.violation_type
            in (ParityViolationType.MISSING_KEY, ParityViolationType.TYPE_MISMATCH)
        ]

    def get_stats(self) -> dict[str, Any]:
        env_counts: dict[str, int] = {}
        for c in self._configs.values():
            env_counts[c.environment] = env_counts.get(c.environment, 0) + 1
        type_counts: dict[str, int] = {}
        for v in self._violations:
            type_counts[v.violation_type] = type_counts.get(v.violation_type, 0) + 1
        return {
            "total_configs": len(self._configs),
            "total_violations": len(self._violations),
            "environment_distribution": env_counts,
            "violation_type_distribution": type_counts,
        }
