"""Incident Root Cause Classifier — classify and track root causes."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RootCauseCategory(StrEnum):
    CODE_DEFECT = "code_defect"
    CONFIGURATION_ERROR = "configuration_error"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    CAPACITY_ISSUE = "capacity_issue"
    DEPENDENCY_FAILURE = "dependency_failure"


class ClassificationConfidence(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SPECULATIVE = "speculative"
    UNCLASSIFIED = "unclassified"


class ClassificationMethod(StrEnum):
    AUTOMATED = "automated"
    MANUAL = "manual"
    HYBRID = "hybrid"
    ML_ASSISTED = "ml_assisted"
    PATTERN_MATCHED = "pattern_matched"


# --- Models ---


class RootCauseRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    incident_id: str = ""
    category: RootCauseCategory = RootCauseCategory.CODE_DEFECT
    confidence: ClassificationConfidence = ClassificationConfidence.MODERATE
    method: ClassificationMethod = ClassificationMethod.AUTOMATED
    root_cause_description: str = ""
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CausePattern(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    category: RootCauseCategory = RootCauseCategory.CODE_DEFECT
    pattern_name: str = ""
    occurrence_count: int = 0
    avg_resolution_minutes: float = 0.0
    created_at: float = Field(default_factory=time.time)


class RootCauseReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_patterns: int = 0
    classification_accuracy_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_causes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentRootCauseClassifier:
    """Classify incident root causes and track patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_pct = min_confidence_pct
        self._records: list[RootCauseRecord] = []
        self._patterns: list[CausePattern] = []
        logger.info(
            "root_cause_classifier.initialized",
            max_records=max_records,
            min_confidence_pct=min_confidence_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_classification(
        self,
        incident_id: str,
        category: RootCauseCategory = (RootCauseCategory.CODE_DEFECT),
        confidence: ClassificationConfidence = (ClassificationConfidence.MODERATE),
        method: ClassificationMethod = (ClassificationMethod.AUTOMATED),
        root_cause_description: str = "",
        service: str = "",
        team: str = "",
    ) -> RootCauseRecord:
        record = RootCauseRecord(
            incident_id=incident_id,
            category=category,
            confidence=confidence,
            method=method,
            root_cause_description=root_cause_description,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "root_cause_classifier.recorded",
            record_id=record.id,
            incident_id=incident_id,
            category=category.value,
            confidence=confidence.value,
        )
        return record

    def get_classification(self, record_id: str) -> RootCauseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_classifications(
        self,
        category: RootCauseCategory | None = None,
        confidence: (ClassificationConfidence | None) = None,
        service: str | None = None,
        limit: int = 50,
    ) -> list[RootCauseRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.category == category]
        if confidence is not None:
            results = [r for r in results if r.confidence == confidence]
        if service is not None:
            results = [r for r in results if r.service == service]
        return results[-limit:]

    def add_cause_pattern(
        self,
        category: RootCauseCategory = (RootCauseCategory.CODE_DEFECT),
        pattern_name: str = "",
        occurrence_count: int = 0,
        avg_resolution_minutes: float = 0.0,
    ) -> CausePattern:
        pattern = CausePattern(
            category=category,
            pattern_name=pattern_name,
            occurrence_count=occurrence_count,
            avg_resolution_minutes=avg_resolution_minutes,
        )
        self._patterns.append(pattern)
        if len(self._patterns) > self._max_records:
            self._patterns = self._patterns[-self._max_records :]
        logger.info(
            "root_cause_classifier.pattern_added",
            pattern_id=pattern.id,
            category=category.value,
            pattern_name=pattern_name,
        )
        return pattern

    # -- domain operations -------------------------------------------

    def analyze_causes_by_category(
        self,
    ) -> list[dict[str, Any]]:
        """Count classifications per category."""
        cat_counts: dict[str, int] = {}
        for r in self._records:
            cat_counts[r.category.value] = cat_counts.get(r.category.value, 0) + 1
        results: list[dict[str, Any]] = []
        for cat, count in cat_counts.items():
            results.append({"category": cat, "count": count})
        results.sort(key=lambda x: x["count"], reverse=True)
        return results

    def identify_low_confidence_classifications(
        self,
    ) -> list[dict[str, Any]]:
        """Find classifications with LOW/SPECULATIVE/UNCLASSIFIED."""
        low_levels = (
            ClassificationConfidence.LOW,
            ClassificationConfidence.SPECULATIVE,
            ClassificationConfidence.UNCLASSIFIED,
        )
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.confidence in low_levels:
                results.append(
                    {
                        "incident_id": r.incident_id,
                        "service": r.service,
                        "confidence": (r.confidence.value),
                        "category": r.category.value,
                    }
                )
        return results

    def rank_by_occurrence(
        self,
    ) -> list[dict[str, Any]]:
        """Rank patterns by occurrence count, desc."""
        results: list[dict[str, Any]] = []
        for p in self._patterns:
            results.append(
                {
                    "pattern_name": p.pattern_name,
                    "category": p.category.value,
                    "occurrence_count": (p.occurrence_count),
                }
            )
        results.sort(
            key=lambda x: x["occurrence_count"],
            reverse=True,
        )
        return results

    def detect_classification_trends(
        self,
    ) -> list[dict[str, Any]]:
        """Detect categories with >3 records."""
        cat_counts: dict[str, int] = {}
        for r in self._records:
            cat_counts[r.category.value] = cat_counts.get(r.category.value, 0) + 1
        results: list[dict[str, Any]] = []
        for cat, count in cat_counts.items():
            if count > 3:
                results.append({"category": cat, "count": count})
        results.sort(key=lambda x: x["count"], reverse=True)
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> RootCauseReport:
        by_category: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            cat = r.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            conf = r.confidence.value
            by_confidence[conf] = by_confidence.get(conf, 0) + 1
            meth = r.method.value
            by_method[meth] = by_method.get(meth, 0) + 1
        total = len(self._records)
        high_conf = sum(1 for r in self._records if r.confidence == ClassificationConfidence.HIGH)
        accuracy = round(high_conf / total * 100.0, 2) if total else 0.0
        # top causes by category count
        sorted_cats = sorted(
            by_category.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        top_causes = [c for c, _ in sorted_cats[:10]]
        recs: list[str] = []
        low_conf = self.identify_low_confidence_classifications()
        if low_conf:
            recs.append(f"{len(low_conf)} low-confidence classification(s) need review")
        if accuracy < self._min_confidence_pct and total:
            recs.append(f"Accuracy {accuracy}% below {self._min_confidence_pct}% target")
        if not recs:
            recs.append("Classification accuracy within acceptable limits")
        return RootCauseReport(
            total_records=total,
            total_patterns=len(self._patterns),
            classification_accuracy_pct=accuracy,
            by_category=by_category,
            by_confidence=by_confidence,
            by_method=by_method,
            top_causes=top_causes,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._patterns.clear()
        logger.info("root_cause_classifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_patterns": len(self._patterns),
            "min_confidence_pct": (self._min_confidence_pct),
            "category_distribution": category_dist,
            "unique_services": len({r.service for r in self._records}),
        }
