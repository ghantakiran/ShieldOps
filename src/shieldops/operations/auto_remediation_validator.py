"""Auto Remediation Validator — validate automated remediation safety and correctness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ValidationMethod(StrEnum):
    PRE_CHECK = "pre_check"
    POST_CHECK = "post_check"
    SMOKE_TEST = "smoke_test"
    HEALTH_CHECK = "health_check"
    ROLLBACK_TEST = "rollback_test"


class ValidationResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class RemediationRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNASSESSED = "unassessed"


# --- Models ---


class RemediationValidation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    validation_method: ValidationMethod = ValidationMethod.PRE_CHECK
    validation_result: ValidationResult = ValidationResult.PASSED
    remediation_risk: RemediationRisk = RemediationRisk.LOW
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ValidationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    validation_method: ValidationMethod = ValidationMethod.PRE_CHECK
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RemediationValidationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_method: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutoRemediationValidator:
    """Validate auto-remediation actions for safety, correctness, and rollback."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[RemediationValidation] = []
        self._analyses: list[ValidationAnalysis] = []
        logger.info(
            "auto_remediation_validator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_validation(
        self,
        service: str,
        validation_method: ValidationMethod = ValidationMethod.PRE_CHECK,
        validation_result: ValidationResult = ValidationResult.PASSED,
        remediation_risk: RemediationRisk = RemediationRisk.LOW,
        score: float = 0.0,
        team: str = "",
    ) -> RemediationValidation:
        record = RemediationValidation(
            validation_method=validation_method,
            validation_result=validation_result,
            remediation_risk=remediation_risk,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "auto_remediation_validator.validation_recorded",
            record_id=record.id,
            service=service,
            validation_method=validation_method.value,
            validation_result=validation_result.value,
        )
        return record

    def get_validation(self, record_id: str) -> RemediationValidation | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_validations(
        self,
        validation_method: ValidationMethod | None = None,
        validation_result: ValidationResult | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RemediationValidation]:
        results = list(self._records)
        if validation_method is not None:
            results = [r for r in results if r.validation_method == validation_method]
        if validation_result is not None:
            results = [r for r in results if r.validation_result == validation_result]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        validation_method: ValidationMethod = ValidationMethod.PRE_CHECK,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ValidationAnalysis:
        analysis = ValidationAnalysis(
            validation_method=validation_method,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "auto_remediation_validator.analysis_added",
            validation_method=validation_method.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by validation_method; return count and avg score."""
        method_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.validation_method.value
            method_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for method, scores in method_data.items():
            result[method] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_validation_gaps(self) -> list[dict[str, Any]]:
        """Return records where score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "validation_method": r.validation_method.value,
                        "score": r.score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_score_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> RemediationValidationReport:
        by_method: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            by_method[r.validation_method.value] = by_method.get(r.validation_method.value, 0) + 1
            by_result[r.validation_result.value] = by_result.get(r.validation_result.value, 0) + 1
            by_risk[r.remediation_risk.value] = by_risk.get(r.remediation_risk.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_validation_gaps()
        top_gaps = [o["service"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} remediation(s) below validation threshold ({self._threshold})"
            )
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Auto-remediation validation coverage is healthy")
        return RemediationValidationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_method=by_method,
            by_result=by_result,
            by_risk=by_risk,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("auto_remediation_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        method_dist: dict[str, int] = {}
        for r in self._records:
            key = r.validation_method.value
            method_dist[key] = method_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "method_distribution": method_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
