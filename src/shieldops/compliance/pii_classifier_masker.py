"""PII Classifier Masker — classify and mask PII data across the platform."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PIIType(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    ADDRESS = "address"


class MaskingMethod(StrEnum):
    REDACT = "redact"
    HASH = "hash"
    TOKENIZE = "tokenize"  # noqa: S105
    ENCRYPT = "encrypt"
    PSEUDONYMIZE = "pseudonymize"


class ClassificationConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"
    MANUAL = "manual"


# --- Models ---


class PIIRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_field: str = ""
    pii_type: PIIType = PIIType.EMAIL
    masking_method: MaskingMethod = MaskingMethod.REDACT
    confidence: ClassificationConfidence = ClassificationConfidence.HIGH
    confidence_score: float = 0.0
    source_system: str = ""
    data_owner: str = ""
    created_at: float = Field(default_factory=time.time)


class MaskingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_field: str = ""
    pii_type: PIIType = PIIType.EMAIL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PIIClassificationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_confidence_score: float = 0.0
    by_pii_type: dict[str, int] = Field(default_factory=dict)
    by_masking_method: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PIIClassifierMasker:
    """Classify and mask PII data; track coverage gaps and masking effectiveness."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[PIIRecord] = []
        self._analyses: list[MaskingAnalysis] = []
        logger.info(
            "pii_classifier_masker.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_pii(
        self,
        data_field: str,
        pii_type: PIIType = PIIType.EMAIL,
        masking_method: MaskingMethod = MaskingMethod.REDACT,
        confidence: ClassificationConfidence = ClassificationConfidence.HIGH,
        confidence_score: float = 0.0,
        source_system: str = "",
        data_owner: str = "",
    ) -> PIIRecord:
        record = PIIRecord(
            data_field=data_field,
            pii_type=pii_type,
            masking_method=masking_method,
            confidence=confidence,
            confidence_score=confidence_score,
            source_system=source_system,
            data_owner=data_owner,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "pii_classifier_masker.pii_recorded",
            record_id=record.id,
            data_field=data_field,
            pii_type=pii_type.value,
            masking_method=masking_method.value,
        )
        return record

    def get_pii(self, record_id: str) -> PIIRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_piis(
        self,
        pii_type: PIIType | None = None,
        masking_method: MaskingMethod | None = None,
        data_owner: str | None = None,
        limit: int = 50,
    ) -> list[PIIRecord]:
        results = list(self._records)
        if pii_type is not None:
            results = [r for r in results if r.pii_type == pii_type]
        if masking_method is not None:
            results = [r for r in results if r.masking_method == masking_method]
        if data_owner is not None:
            results = [r for r in results if r.data_owner == data_owner]
        return results[-limit:]

    def add_analysis(
        self,
        data_field: str,
        pii_type: PIIType = PIIType.EMAIL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MaskingAnalysis:
        analysis = MaskingAnalysis(
            data_field=data_field,
            pii_type=pii_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "pii_classifier_masker.analysis_added",
            data_field=data_field,
            pii_type=pii_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_pii_distribution(self) -> dict[str, Any]:
        """Group by pii_type; return count and avg confidence_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.pii_type.value
            type_data.setdefault(key, []).append(r.confidence_score)
        result: dict[str, Any] = {}
        for ptype, scores in type_data.items():
            result[ptype] = {
                "count": len(scores),
                "avg_confidence_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_masking_gaps(self) -> list[dict[str, Any]]:
        """Return records where confidence_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.confidence_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "data_field": r.data_field,
                        "pii_type": r.pii_type.value,
                        "confidence_score": r.confidence_score,
                        "source_system": r.source_system,
                        "data_owner": r.data_owner,
                    }
                )
        return sorted(results, key=lambda x: x["confidence_score"])

    def rank_by_confidence(self) -> list[dict[str, Any]]:
        """Group by source_system, avg confidence_score, sort ascending."""
        sys_scores: dict[str, list[float]] = {}
        for r in self._records:
            sys_scores.setdefault(r.source_system, []).append(r.confidence_score)
        results: list[dict[str, Any]] = []
        for sys, scores in sys_scores.items():
            results.append(
                {
                    "source_system": sys,
                    "avg_confidence_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_confidence_score"])
        return results

    def detect_classification_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> PIIClassificationReport:
        by_pii_type: dict[str, int] = {}
        by_masking_method: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_pii_type[r.pii_type.value] = by_pii_type.get(r.pii_type.value, 0) + 1
            by_masking_method[r.masking_method.value] = (
                by_masking_method.get(r.masking_method.value, 0) + 1
            )
            by_confidence[r.confidence.value] = by_confidence.get(r.confidence.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.confidence_score < self._threshold)
        scores = [r.confidence_score for r in self._records]
        avg_confidence_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_masking_gaps()
        top_gaps = [o["data_field"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} field(s) below classification threshold ({self._threshold})")
        if self._records and avg_confidence_score < self._threshold:
            recs.append(
                f"Avg confidence score {avg_confidence_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("PII classification coverage is healthy")
        return PIIClassificationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_confidence_score=avg_confidence_score,
            by_pii_type=by_pii_type,
            by_masking_method=by_masking_method,
            by_confidence=by_confidence,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("pii_classifier_masker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.pii_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "pii_type_distribution": type_dist,
            "unique_owners": len({r.data_owner for r in self._records}),
            "unique_systems": len({r.source_system for r in self._records}),
        }
