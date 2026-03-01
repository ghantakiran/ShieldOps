"""Service Dependency Validator — validate deps against traffic."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ValidationResult(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    UNDECLARED = "undeclared"
    STALE = "stale"
    PARTIAL = "partial"


class DependencyDirection(StrEnum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    BIDIRECTIONAL = "bidirectional"
    CIRCULAR = "circular"
    UNKNOWN = "unknown"


class ValidationSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFO = "info"


# --- Models ---


class ValidationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    dependency: str = ""
    result: ValidationResult = ValidationResult.VALID
    direction: DependencyDirection = DependencyDirection.UNKNOWN
    severity: ValidationSeverity = ValidationSeverity.INFO
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ValidationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_pattern: str = ""
    result: ValidationResult = ValidationResult.VALID
    direction: DependencyDirection = DependencyDirection.UNKNOWN
    threshold_pct: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyValidationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    invalid_count: int = 0
    undeclared_count: int = 0
    by_result: dict[str, int] = Field(default_factory=dict)
    by_direction: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    high_risk_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceDependencyValidator:
    """Validate declared deps against actual traffic."""

    def __init__(
        self,
        max_records: int = 200000,
        max_invalid_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_invalid_pct = max_invalid_pct
        self._records: list[ValidationRecord] = []
        self._rules: list[ValidationRule] = []
        logger.info(
            "dep_validator.initialized",
            max_records=max_records,
            max_invalid_pct=max_invalid_pct,
        )

    # -- record / get / list -----------------------------------------------

    def record_validation(
        self,
        service: str,
        dependency: str = "",
        result: ValidationResult = ValidationResult.VALID,
        direction: DependencyDirection = (DependencyDirection.UNKNOWN),
        severity: ValidationSeverity = (ValidationSeverity.INFO),
        team: str = "",
        details: str = "",
    ) -> ValidationRecord:
        record = ValidationRecord(
            service=service,
            dependency=dependency,
            result=result,
            direction=direction,
            severity=severity,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dep_validator.validation_recorded",
            record_id=record.id,
            service=service,
            result=result.value,
            direction=direction.value,
        )
        return record

    def get_validation(self, record_id: str) -> ValidationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_validations(
        self,
        result: ValidationResult | None = None,
        direction: DependencyDirection | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ValidationRecord]:
        results = list(self._records)
        if result is not None:
            results = [r for r in results if r.result == result]
        if direction is not None:
            results = [r for r in results if r.direction == direction]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        service_pattern: str,
        result: ValidationResult = ValidationResult.VALID,
        direction: DependencyDirection = (DependencyDirection.UNKNOWN),
        threshold_pct: float = 0.0,
        reason: str = "",
    ) -> ValidationRule:
        rule = ValidationRule(
            service_pattern=service_pattern,
            result=result,
            direction=direction,
            threshold_pct=threshold_pct,
            reason=reason,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "dep_validator.rule_added",
            service_pattern=service_pattern,
            result=result.value,
            threshold_pct=threshold_pct,
        )
        return rule

    # -- domain operations -------------------------------------------------

    def analyze_validation_results(
        self,
    ) -> dict[str, Any]:
        """Group by result; count and avg severity."""
        sev_map = {
            ValidationSeverity.CRITICAL: 5,
            ValidationSeverity.HIGH: 4,
            ValidationSeverity.MODERATE: 3,
            ValidationSeverity.LOW: 2,
            ValidationSeverity.INFO: 1,
        }
        result_data: dict[str, list[int]] = {}
        for r in self._records:
            key = r.result.value
            result_data.setdefault(key, []).append(sev_map.get(r.severity, 1))
        out: dict[str, Any] = {}
        for res, scores in result_data.items():
            out[res] = {
                "count": len(scores),
                "avg_severity": round(sum(scores) / len(scores), 2),
            }
        return out

    def identify_undeclared_deps(
        self,
    ) -> list[dict[str, Any]]:
        """Return records where result == UNDECLARED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.result == ValidationResult.UNDECLARED:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "dependency": r.dependency,
                        "direction": r.direction.value,
                        "severity": r.severity.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_invalid_count(
        self,
    ) -> list[dict[str, Any]]:
        """Group by service, count invalids, sort desc."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.result == ValidationResult.INVALID:
                svc_counts[r.service] = svc_counts.get(r.service, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            results.append(
                {
                    "service": svc,
                    "invalid_count": count,
                }
            )
        results.sort(key=lambda x: x["invalid_count"], reverse=True)
        return results

    def detect_validation_trends(
        self,
    ) -> dict[str, Any]:
        """Split-half comparison on threshold_pct."""
        if len(self._rules) < 2:
            return {
                "trend": "insufficient_data",
                "delta": 0.0,
            }
        vals = [ru.threshold_pct for ru in self._rules]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats ----------------------------------------------------

    def generate_report(self) -> DependencyValidationReport:
        by_result: dict[str, int] = {}
        by_direction: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_result[r.result.value] = by_result.get(r.result.value, 0) + 1
            by_direction[r.direction.value] = by_direction.get(r.direction.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
        invalid_count = sum(1 for r in self._records if r.result == ValidationResult.INVALID)
        undeclared_count = sum(1 for r in self._records if r.result == ValidationResult.UNDECLARED)
        rankings = self.rank_by_invalid_count()
        high_risk = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if self._records:
            invalid_pct = round(
                invalid_count / len(self._records) * 100,
                2,
            )
            if invalid_pct > self._max_invalid_pct:
                recs.append(
                    f"Invalid rate {invalid_pct}% exceeds threshold ({self._max_invalid_pct}%)"
                )
        if undeclared_count > 0:
            recs.append(f"{undeclared_count} undeclared dep(s) — update service catalog")
        if not recs:
            recs.append("Dependency validation levels are healthy")
        return DependencyValidationReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            invalid_count=invalid_count,
            undeclared_count=undeclared_count,
            by_result=by_result,
            by_direction=by_direction,
            by_severity=by_severity,
            high_risk_services=high_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("dep_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        result_dist: dict[str, int] = {}
        for r in self._records:
            key = r.result.value
            result_dist[key] = result_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "max_invalid_pct": self._max_invalid_pct,
            "result_distribution": result_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
