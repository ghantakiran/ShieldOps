"""Incident Severity Validator — validate and audit incident severity classifications."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SeverityLevel(StrEnum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"
    SEV5 = "sev5"


class ValidationOutcome(StrEnum):
    CORRECT = "correct"
    OVER_CLASSIFIED = "over_classified"
    UNDER_CLASSIFIED = "under_classified"
    NEEDS_REVIEW = "needs_review"
    INCONCLUSIVE = "inconclusive"


class SeverityCriteria(StrEnum):
    USER_IMPACT = "user_impact"
    REVENUE_IMPACT = "revenue_impact"
    DATA_LOSS = "data_loss"
    SERVICE_DEGRADATION = "service_degradation"
    SECURITY_BREACH = "security_breach"


# --- Models ---


class SeverityValidationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    assigned_severity: SeverityLevel = SeverityLevel.SEV3
    validated_severity: SeverityLevel = SeverityLevel.SEV3
    outcome: ValidationOutcome = ValidationOutcome.CORRECT
    criteria: SeverityCriteria = SeverityCriteria.SERVICE_DEGRADATION
    accuracy_score: float = 100.0
    validator_id: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ValidationCriterion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    criteria: SeverityCriteria = SeverityCriteria.SERVICE_DEGRADATION
    severity_level: SeverityLevel = SeverityLevel.SEV3
    threshold_description: str = ""
    weight: float = 1.0
    active: bool = True
    created_at: float = Field(default_factory=time.time)


class SeverityValidatorReport(BaseModel):
    total_validations: int = 0
    total_criteria: int = 0
    accuracy_pct: float = 0.0
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    misclassified_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentSeverityValidator:
    """Validate and audit incident severity classifications."""

    def __init__(
        self,
        max_records: int = 200000,
        min_accuracy_pct: float = 85.0,
    ) -> None:
        self._max_records = max_records
        self._min_accuracy_pct = min_accuracy_pct
        self._records: list[SeverityValidationRecord] = []
        self._criteria: list[ValidationCriterion] = []
        logger.info(
            "severity_validator.initialized",
            max_records=max_records,
            min_accuracy_pct=min_accuracy_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_validation(
        self,
        incident_id: str,
        assigned_severity: SeverityLevel = SeverityLevel.SEV3,
        validated_severity: SeverityLevel = SeverityLevel.SEV3,
        outcome: ValidationOutcome = ValidationOutcome.CORRECT,
        criteria: SeverityCriteria = SeverityCriteria.SERVICE_DEGRADATION,
        accuracy_score: float = 100.0,
        validator_id: str = "",
        details: str = "",
    ) -> SeverityValidationRecord:
        record = SeverityValidationRecord(
            incident_id=incident_id,
            assigned_severity=assigned_severity,
            validated_severity=validated_severity,
            outcome=outcome,
            criteria=criteria,
            accuracy_score=accuracy_score,
            validator_id=validator_id,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "severity_validator.validation_recorded",
            record_id=record.id,
            incident_id=incident_id,
            assigned_severity=assigned_severity.value,
            outcome=outcome.value,
        )
        return record

    def get_validation(self, record_id: str) -> SeverityValidationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_validations(
        self,
        incident_id: str | None = None,
        outcome: ValidationOutcome | None = None,
        limit: int = 50,
    ) -> list[SeverityValidationRecord]:
        results = list(self._records)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        if outcome is not None:
            results = [r for r in results if r.outcome == outcome]
        return results[-limit:]

    def add_criterion(
        self,
        criteria: SeverityCriteria = SeverityCriteria.SERVICE_DEGRADATION,
        severity_level: SeverityLevel = SeverityLevel.SEV3,
        threshold_description: str = "",
        weight: float = 1.0,
        active: bool = True,
    ) -> ValidationCriterion:
        criterion = ValidationCriterion(
            criteria=criteria,
            severity_level=severity_level,
            threshold_description=threshold_description,
            weight=weight,
            active=active,
        )
        self._criteria.append(criterion)
        if len(self._criteria) > self._max_records:
            self._criteria = self._criteria[-self._max_records :]
        logger.info(
            "severity_validator.criterion_added",
            criteria=criteria.value,
            severity_level=severity_level.value,
            weight=weight,
        )
        return criterion

    # -- domain operations -----------------------------------------------

    def analyze_validation_accuracy(self, validator_id: str) -> dict[str, Any]:
        """Analyze classification accuracy for a specific validator."""
        records = [r for r in self._records if r.validator_id == validator_id]
        if not records:
            return {"validator_id": validator_id, "status": "no_data"}
        correct = sum(1 for r in records if r.outcome == ValidationOutcome.CORRECT)
        accuracy = round(correct / len(records) * 100, 2)
        avg_score = round(sum(r.accuracy_score for r in records) / len(records), 2)
        return {
            "validator_id": validator_id,
            "total_validations": len(records),
            "correct_count": correct,
            "accuracy_pct": accuracy,
            "avg_accuracy_score": avg_score,
            "meets_threshold": accuracy >= self._min_accuracy_pct,
        }

    def identify_misclassified_incidents(self) -> list[dict[str, Any]]:
        """Find incidents with non-correct validation outcomes."""
        results: list[dict[str, Any]] = []
        misclassified_outcomes = (
            ValidationOutcome.OVER_CLASSIFIED,
            ValidationOutcome.UNDER_CLASSIFIED,
        )
        for r in self._records:
            if r.outcome in misclassified_outcomes:
                results.append(
                    {
                        "incident_id": r.incident_id,
                        "assigned_severity": r.assigned_severity.value,
                        "validated_severity": r.validated_severity.value,
                        "outcome": r.outcome.value,
                        "accuracy_score": r.accuracy_score,
                    }
                )
        results.sort(key=lambda x: x["accuracy_score"])
        return results

    def rank_by_accuracy_score(self) -> list[dict[str, Any]]:
        """Rank validation records by accuracy score descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "incident_id": r.incident_id,
                    "accuracy_score": r.accuracy_score,
                    "outcome": r.outcome.value,
                    "assigned_severity": r.assigned_severity.value,
                }
            )
        results.sort(key=lambda x: x["accuracy_score"], reverse=True)
        return results

    def detect_classification_bias(self) -> list[dict[str, Any]]:
        """Detect systematic over/under-classification bias by severity level."""
        over_by_sev: dict[str, int] = {}
        under_by_sev: dict[str, int] = {}
        total_by_sev: dict[str, int] = {}
        for r in self._records:
            key = r.assigned_severity.value
            total_by_sev[key] = total_by_sev.get(key, 0) + 1
            if r.outcome == ValidationOutcome.OVER_CLASSIFIED:
                over_by_sev[key] = over_by_sev.get(key, 0) + 1
            elif r.outcome == ValidationOutcome.UNDER_CLASSIFIED:
                under_by_sev[key] = under_by_sev.get(key, 0) + 1
        results: list[dict[str, Any]] = []
        for sev, total in total_by_sev.items():
            over = over_by_sev.get(sev, 0)
            under = under_by_sev.get(sev, 0)
            over_pct = round(over / total * 100, 2)
            under_pct = round(under / total * 100, 2)
            if over_pct > 20 or under_pct > 20:
                results.append(
                    {
                        "severity_level": sev,
                        "total": total,
                        "over_classified_pct": over_pct,
                        "under_classified_pct": under_pct,
                        "bias_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["over_classified_pct"] + x["under_classified_pct"], reverse=True
        )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> SeverityValidatorReport:
        by_outcome: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
            by_severity[r.assigned_severity.value] = (
                by_severity.get(r.assigned_severity.value, 0) + 1
            )
        correct_count = sum(1 for r in self._records if r.outcome == ValidationOutcome.CORRECT)
        accuracy = round(correct_count / len(self._records) * 100, 2) if self._records else 0.0
        misclassified = self.identify_misclassified_incidents()
        bias = self.detect_classification_bias()
        recs: list[str] = []
        if accuracy < self._min_accuracy_pct:
            recs.append(f"Accuracy {accuracy}% is below {self._min_accuracy_pct}% threshold")
        if misclassified:
            recs.append(f"{len(misclassified)} incident(s) with confirmed misclassification")
        if bias:
            recs.append(f"{len(bias)} severity level(s) with systematic classification bias")
        if not recs:
            recs.append("Severity classification accuracy meets targets")
        return SeverityValidatorReport(
            total_validations=len(self._records),
            total_criteria=len(self._criteria),
            accuracy_pct=accuracy,
            by_outcome=by_outcome,
            by_severity=by_severity,
            misclassified_count=len(misclassified),
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._criteria.clear()
        logger.info("severity_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        outcome_dist: dict[str, int] = {}
        for r in self._records:
            key = r.outcome.value
            outcome_dist[key] = outcome_dist.get(key, 0) + 1
        return {
            "total_validations": len(self._records),
            "total_criteria": len(self._criteria),
            "min_accuracy_pct": self._min_accuracy_pct,
            "outcome_distribution": outcome_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
