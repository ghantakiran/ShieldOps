"""Metric Anomaly Classifier — classify metric anomalies by type and confidence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AnomalyType(StrEnum):
    SPIKE = "spike"
    DRIFT = "drift"
    SEASONAL_DEVIATION = "seasonal_deviation"
    NOISE = "noise"
    STEP_CHANGE = "step_change"


class AnomalyConfidence(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class AnomalyImpact(StrEnum):
    CRITICAL = "critical"
    SIGNIFICANT = "significant"
    MODERATE = "moderate"
    MINOR = "minor"
    NEGLIGIBLE = "negligible"


# --- Models ---


class AnomalyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    anomaly_type: AnomalyType = AnomalyType.SPIKE
    anomaly_confidence: AnomalyConfidence = AnomalyConfidence.VERY_HIGH
    anomaly_impact: AnomalyImpact = AnomalyImpact.CRITICAL
    confidence_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ClassificationResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    anomaly_type: AnomalyType = AnomalyType.SPIKE
    classification_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MetricAnomalyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_classifications: int = 0
    low_confidence_count: int = 0
    avg_confidence_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    top_low_confidence: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MetricAnomalyClassifier:
    """Classify metric anomalies, detect low-confidence classifications, track trends."""

    def __init__(
        self,
        max_records: int = 200000,
        confidence_threshold: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._confidence_threshold = confidence_threshold
        self._records: list[AnomalyRecord] = []
        self._classifications: list[ClassificationResult] = []
        logger.info(
            "metric_anomaly_classifier.initialized",
            max_records=max_records,
            confidence_threshold=confidence_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_anomaly(
        self,
        metric_name: str,
        anomaly_type: AnomalyType = AnomalyType.SPIKE,
        anomaly_confidence: AnomalyConfidence = AnomalyConfidence.VERY_HIGH,
        anomaly_impact: AnomalyImpact = AnomalyImpact.CRITICAL,
        confidence_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AnomalyRecord:
        record = AnomalyRecord(
            metric_name=metric_name,
            anomaly_type=anomaly_type,
            anomaly_confidence=anomaly_confidence,
            anomaly_impact=anomaly_impact,
            confidence_score=confidence_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "metric_anomaly_classifier.anomaly_recorded",
            record_id=record.id,
            metric_name=metric_name,
            anomaly_type=anomaly_type.value,
            anomaly_confidence=anomaly_confidence.value,
        )
        return record

    def get_anomaly(self, record_id: str) -> AnomalyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_anomalies(
        self,
        anomaly_type: AnomalyType | None = None,
        anomaly_confidence: AnomalyConfidence | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AnomalyRecord]:
        results = list(self._records)
        if anomaly_type is not None:
            results = [r for r in results if r.anomaly_type == anomaly_type]
        if anomaly_confidence is not None:
            results = [r for r in results if r.anomaly_confidence == anomaly_confidence]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_classification(
        self,
        metric_name: str,
        anomaly_type: AnomalyType = AnomalyType.SPIKE,
        classification_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ClassificationResult:
        classification = ClassificationResult(
            metric_name=metric_name,
            anomaly_type=anomaly_type,
            classification_score=classification_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._classifications.append(classification)
        if len(self._classifications) > self._max_records:
            self._classifications = self._classifications[-self._max_records :]
        logger.info(
            "metric_anomaly_classifier.classification_added",
            metric_name=metric_name,
            anomaly_type=anomaly_type.value,
            classification_score=classification_score,
        )
        return classification

    # -- domain operations --------------------------------------------------

    def analyze_anomaly_distribution(self) -> dict[str, Any]:
        """Group by anomaly_type; return count and avg score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.anomaly_type.value
            type_data.setdefault(key, []).append(r.confidence_score)
        result: dict[str, Any] = {}
        for atype, scores in type_data.items():
            result[atype] = {
                "count": len(scores),
                "avg_confidence_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_confidence_anomalies(self) -> list[dict[str, Any]]:
        """Return anomalies where confidence_score < confidence_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.confidence_score < self._confidence_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "metric_name": r.metric_name,
                        "anomaly_type": r.anomaly_type.value,
                        "anomaly_confidence": r.anomaly_confidence.value,
                        "confidence_score": r.confidence_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["confidence_score"], reverse=False)
        return results

    def rank_by_confidence(self) -> list[dict[str, Any]]:
        """Group by service, avg confidence_score, sort asc (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.confidence_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_confidence_score": round(sum(scores) / len(scores), 2),
                    "anomaly_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_confidence_score"], reverse=False)
        return results

    def detect_anomaly_trends(self) -> dict[str, Any]:
        """Split-half comparison on classification_score; delta 5.0."""
        if len(self._classifications) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [c.classification_score for c in self._classifications]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> MetricAnomalyReport:
        by_type: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        for r in self._records:
            by_type[r.anomaly_type.value] = by_type.get(r.anomaly_type.value, 0) + 1
            by_confidence[r.anomaly_confidence.value] = (
                by_confidence.get(r.anomaly_confidence.value, 0) + 1
            )
            by_impact[r.anomaly_impact.value] = by_impact.get(r.anomaly_impact.value, 0) + 1
        low_confidence_count = sum(
            1 for r in self._records if r.confidence_score < self._confidence_threshold
        )
        avg_confidence = (
            round(
                sum(r.confidence_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        low_conf = self.identify_low_confidence_anomalies()
        top_low_confidence = [p["metric_name"] for p in low_conf]
        recs: list[str] = []
        if low_conf:
            recs.append(
                f"{len(low_conf)} low-confidence anomaly(ies) detected — review classifiers"
            )
        below = sum(1 for r in self._records if r.confidence_score < self._confidence_threshold)
        if below > 0:
            recs.append(
                f"{below} anomaly(ies) below confidence threshold ({self._confidence_threshold}%)"
            )
        if not recs:
            recs.append("Anomaly classification confidence levels are acceptable")
        return MetricAnomalyReport(
            total_records=len(self._records),
            total_classifications=len(self._classifications),
            low_confidence_count=low_confidence_count,
            avg_confidence_score=avg_confidence,
            by_type=by_type,
            by_confidence=by_confidence,
            by_impact=by_impact,
            top_low_confidence=top_low_confidence,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._classifications.clear()
        logger.info("metric_anomaly_classifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.anomaly_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_classifications": len(self._classifications),
            "confidence_threshold": self._confidence_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
