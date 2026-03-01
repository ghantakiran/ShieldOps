"""Data Classification Engine — classify data, track rules, and detect drift."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DataSensitivity(StrEnum):
    TOP_SECRET = "top_secret"  # noqa: S105
    CONFIDENTIAL = "confidential"
    INTERNAL = "internal"
    PUBLIC = "public"
    UNCLASSIFIED = "unclassified"


class ClassificationStatus(StrEnum):
    CLASSIFIED = "classified"
    PENDING = "pending"
    NEEDS_REVIEW = "needs_review"
    RECLASSIFIED = "reclassified"
    EXEMPT = "exempt"


class DataCategory(StrEnum):
    PII = "pii"
    FINANCIAL = "financial"
    HEALTHCARE = "healthcare"
    CREDENTIALS = "credentials"
    OPERATIONAL = "operational"


# --- Models ---


class ClassificationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    classification_id: str = ""
    data_sensitivity: DataSensitivity = DataSensitivity.UNCLASSIFIED
    classification_status: ClassificationStatus = ClassificationStatus.PENDING
    data_category: DataCategory = DataCategory.OPERATIONAL
    coverage_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ClassificationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    classification_id: str = ""
    data_sensitivity: DataSensitivity = DataSensitivity.UNCLASSIFIED
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DataClassificationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    unclassified_data: int = 0
    avg_coverage_pct: float = 0.0
    by_sensitivity: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_unclassified: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataClassificationEngine:
    """Classify data, identify coverage gaps, and detect classification drift."""

    def __init__(
        self,
        max_records: int = 200000,
        min_classification_coverage_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_classification_coverage_pct = min_classification_coverage_pct
        self._records: list[ClassificationRecord] = []
        self._rules: list[ClassificationRule] = []
        logger.info(
            "data_classification.initialized",
            max_records=max_records,
            min_classification_coverage_pct=min_classification_coverage_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_classification(
        self,
        classification_id: str,
        data_sensitivity: DataSensitivity = DataSensitivity.UNCLASSIFIED,
        classification_status: ClassificationStatus = ClassificationStatus.PENDING,
        data_category: DataCategory = DataCategory.OPERATIONAL,
        coverage_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ClassificationRecord:
        record = ClassificationRecord(
            classification_id=classification_id,
            data_sensitivity=data_sensitivity,
            classification_status=classification_status,
            data_category=data_category,
            coverage_pct=coverage_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_classification.classification_recorded",
            record_id=record.id,
            classification_id=classification_id,
            data_sensitivity=data_sensitivity.value,
            classification_status=classification_status.value,
        )
        return record

    def get_classification(self, record_id: str) -> ClassificationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_classifications(
        self,
        sensitivity: DataSensitivity | None = None,
        status: ClassificationStatus | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ClassificationRecord]:
        results = list(self._records)
        if sensitivity is not None:
            results = [r for r in results if r.data_sensitivity == sensitivity]
        if status is not None:
            results = [r for r in results if r.classification_status == status]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        classification_id: str,
        data_sensitivity: DataSensitivity = DataSensitivity.UNCLASSIFIED,
        value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ClassificationRule:
        rule = ClassificationRule(
            classification_id=classification_id,
            data_sensitivity=data_sensitivity,
            value=value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "data_classification.rule_added",
            classification_id=classification_id,
            data_sensitivity=data_sensitivity.value,
            value=value,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_classification_coverage(self) -> dict[str, Any]:
        """Group by sensitivity; return count and avg coverage per sensitivity."""
        sensitivity_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.data_sensitivity.value
            sensitivity_data.setdefault(key, []).append(r.coverage_pct)
        result: dict[str, Any] = {}
        for sensitivity, coverages in sensitivity_data.items():
            result[sensitivity] = {
                "count": len(coverages),
                "avg_coverage_pct": round(sum(coverages) / len(coverages), 2),
            }
        return result

    def identify_unclassified_data(self) -> list[dict[str, Any]]:
        """Return records where status == PENDING or NEEDS_REVIEW."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.classification_status in (
                ClassificationStatus.PENDING,
                ClassificationStatus.NEEDS_REVIEW,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "classification_id": r.classification_id,
                        "data_sensitivity": r.data_sensitivity.value,
                        "classification_status": r.classification_status.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_sensitivity(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg coverage."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.coverage_pct)
        results: list[dict[str, Any]] = []
        for service, coverages in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(coverages),
                    "avg_coverage_pct": round(sum(coverages) / len(coverages), 2),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_pct"], reverse=True)
        return results

    def detect_classification_drift(self) -> dict[str, Any]:
        """Split-half on value; delta threshold 5.0."""
        if len(self._rules) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [r.value for r in self._rules]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
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

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DataClassificationReport:
        by_sensitivity: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_sensitivity[r.data_sensitivity.value] = (
                by_sensitivity.get(r.data_sensitivity.value, 0) + 1
            )
            by_status[r.classification_status.value] = (
                by_status.get(r.classification_status.value, 0) + 1
            )
            by_category[r.data_category.value] = by_category.get(r.data_category.value, 0) + 1
        unclassified_count = sum(
            1
            for r in self._records
            if r.classification_status
            in (ClassificationStatus.PENDING, ClassificationStatus.NEEDS_REVIEW)
        )
        coverages = [r.coverage_pct for r in self._records]
        avg_coverage = round(sum(coverages) / len(coverages), 2) if coverages else 0.0
        rankings = self.rank_by_sensitivity()
        top_unclassified = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        below_threshold = sum(
            1 for r in self._records if r.coverage_pct < self._min_classification_coverage_pct
        )
        below_rate = round(below_threshold / len(self._records) * 100, 2) if self._records else 0.0
        if below_rate > 20.0:
            recs.append(
                f"Low coverage rate {below_rate}% exceeds threshold"
                f" ({self._min_classification_coverage_pct})"
            )
        if unclassified_count > 0:
            recs.append(
                f"{unclassified_count} unclassified record(s) detected — review classifications"
            )
        if not recs:
            recs.append("Data classification coverage is acceptable")
        return DataClassificationReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            unclassified_data=unclassified_count,
            avg_coverage_pct=avg_coverage,
            by_sensitivity=by_sensitivity,
            by_status=by_status,
            by_category=by_category,
            top_unclassified=top_unclassified,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("data_classification.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        sensitivity_dist: dict[str, int] = {}
        for r in self._records:
            key = r.data_sensitivity.value
            sensitivity_dist[key] = sensitivity_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "min_classification_coverage_pct": self._min_classification_coverage_pct,
            "sensitivity_distribution": sensitivity_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_classifications": len({r.classification_id for r in self._records}),
        }
