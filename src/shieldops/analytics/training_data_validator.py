"""Training Data Validator — validate training data quality for ML models."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ValidationCheck(StrEnum):
    SCHEMA = "schema"
    DISTRIBUTION = "distribution"
    OUTLIER = "outlier"
    MISSING = "missing"
    BIAS = "bias"


class DataQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNACCEPTABLE = "unacceptable"


class ValidationStatus(StrEnum):
    PASSED = "passed"  # noqa: S105
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    IN_PROGRESS = "in_progress"


# --- Models ---


class ValidationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dataset_id: str = ""
    model_id: str = ""
    validation_check: ValidationCheck = ValidationCheck.SCHEMA
    data_quality: DataQuality = DataQuality.ACCEPTABLE
    validation_status: ValidationStatus = ValidationStatus.IN_PROGRESS
    quality_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ValidationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dataset_id: str = ""
    validation_check: ValidationCheck = ValidationCheck.SCHEMA
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ValidationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    failed_count: int = 0
    avg_quality_score: float = 0.0
    by_check: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_failures: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TrainingDataValidator:
    """Validate training data quality for ML models."""

    def __init__(
        self,
        max_records: int = 200000,
        quality_threshold: float = 0.75,
    ) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[ValidationRecord] = []
        self._analyses: list[ValidationAnalysis] = []
        logger.info(
            "training_data_validator.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_validation(
        self,
        dataset_id: str,
        model_id: str = "",
        validation_check: ValidationCheck = ValidationCheck.SCHEMA,
        data_quality: DataQuality = DataQuality.ACCEPTABLE,
        validation_status: ValidationStatus = ValidationStatus.IN_PROGRESS,
        quality_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ValidationRecord:
        record = ValidationRecord(
            dataset_id=dataset_id,
            model_id=model_id,
            validation_check=validation_check,
            data_quality=data_quality,
            validation_status=validation_status,
            quality_score=quality_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "training_data_validator.validation_recorded",
            record_id=record.id,
            dataset_id=dataset_id,
            validation_check=validation_check.value,
        )
        return record

    def get_validation(self, record_id: str) -> ValidationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_validations(
        self,
        validation_check: ValidationCheck | None = None,
        validation_status: ValidationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ValidationRecord]:
        results = list(self._records)
        if validation_check is not None:
            results = [r for r in results if r.validation_check == validation_check]
        if validation_status is not None:
            results = [r for r in results if r.validation_status == validation_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        dataset_id: str,
        validation_check: ValidationCheck = ValidationCheck.SCHEMA,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ValidationAnalysis:
        analysis = ValidationAnalysis(
            dataset_id=dataset_id,
            validation_check=validation_check,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "training_data_validator.analysis_added",
            dataset_id=dataset_id,
            validation_check=validation_check.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by validation_check; return count and avg quality_score."""
        check_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.validation_check.value
            check_data.setdefault(key, []).append(r.quality_score)
        result: dict[str, Any] = {}
        for check, scores in check_data.items():
            result[check] = {
                "count": len(scores),
                "avg_quality_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_severe_drifts(self) -> list[dict[str, Any]]:
        """Return records where quality_score < quality_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.quality_score < self._quality_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "dataset_id": r.dataset_id,
                        "validation_check": r.validation_check.value,
                        "quality_score": r.quality_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["quality_score"])

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by dataset_id, avg quality_score, sort ascending (lowest first)."""
        dataset_scores: dict[str, list[float]] = {}
        for r in self._records:
            dataset_scores.setdefault(r.dataset_id, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for dataset_id, scores in dataset_scores.items():
            results.append(
                {
                    "dataset_id": dataset_id,
                    "avg_quality_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_quality_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ValidationReport:
        by_check: dict[str, int] = {}
        by_quality: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_check[r.validation_check.value] = by_check.get(r.validation_check.value, 0) + 1
            by_quality[r.data_quality.value] = by_quality.get(r.data_quality.value, 0) + 1
            by_status[r.validation_status.value] = by_status.get(r.validation_status.value, 0) + 1
        failed_count = sum(1 for r in self._records if r.quality_score < self._quality_threshold)
        scores = [r.quality_score for r in self._records]
        avg_quality_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        failure_list = self.identify_severe_drifts()
        top_failures = [o["dataset_id"] for o in failure_list[:5]]
        recs: list[str] = []
        if self._records and failed_count > 0:
            recs.append(
                f"{failed_count} dataset(s) below quality threshold ({self._quality_threshold})"
            )
        if self._records and avg_quality_score < self._quality_threshold:
            recs.append(
                f"Avg quality score {avg_quality_score} below threshold ({self._quality_threshold})"
            )
        if not recs:
            recs.append("Training data quality is within acceptable bounds")
        return ValidationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            failed_count=failed_count,
            avg_quality_score=avg_quality_score,
            by_check=by_check,
            by_quality=by_quality,
            by_status=by_status,
            top_failures=top_failures,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("training_data_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        check_dist: dict[str, int] = {}
        for r in self._records:
            key = r.validation_check.value
            check_dist[key] = check_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "quality_threshold": self._quality_threshold,
            "check_distribution": check_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_datasets": len({r.dataset_id for r in self._records}),
        }
