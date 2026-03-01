"""Metric Anomaly Scorer — track and analyze metric anomaly scores."""

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
    DROP = "drop"
    DRIFT = "drift"
    OSCILLATION = "oscillation"
    FLATLINE = "flatline"


class AnomalySeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    NOISE = "noise"


class AnomalySource(StrEnum):
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"
    NETWORK = "network"
    DATABASE = "database"
    EXTERNAL = "external"


# --- Models ---


class AnomalyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    anomaly_type: AnomalyType = AnomalyType.SPIKE
    severity: AnomalySeverity = AnomalySeverity.NOISE
    source: AnomalySource = AnomalySource.APPLICATION
    anomaly_score: float = 0.0
    service: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class AnomalyContext(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    record_id: str = ""
    context_metric: str = ""
    correlation_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MetricAnomalyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_contexts: int = 0
    critical_anomalies: int = 0
    avg_anomaly_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    top_anomalies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MetricAnomalyScorer:
    """Track and analyze metric anomaly scores."""

    def __init__(
        self,
        max_records: int = 200000,
        min_anomaly_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_anomaly_score = min_anomaly_score
        self._records: list[AnomalyRecord] = []
        self._contexts: list[AnomalyContext] = []
        logger.info(
            "anomaly_scorer.initialized",
            max_records=max_records,
            min_anomaly_score=min_anomaly_score,
        )

    # -- record / get / list ---------------------------------------------

    def record_anomaly(
        self,
        metric_name: str,
        anomaly_type: AnomalyType = AnomalyType.SPIKE,
        severity: AnomalySeverity = AnomalySeverity.NOISE,
        source: AnomalySource = AnomalySource.APPLICATION,
        anomaly_score: float = 0.0,
        service: str = "",
        details: str = "",
    ) -> AnomalyRecord:
        record = AnomalyRecord(
            metric_name=metric_name,
            anomaly_type=anomaly_type,
            severity=severity,
            source=source,
            anomaly_score=anomaly_score,
            service=service,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "anomaly_scorer.recorded",
            record_id=record.id,
            metric_name=metric_name,
            severity=severity.value,
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
        severity: AnomalySeverity | None = None,
        source: AnomalySource | None = None,
        limit: int = 50,
    ) -> list[AnomalyRecord]:
        results = list(self._records)
        if anomaly_type is not None:
            results = [r for r in results if r.anomaly_type == anomaly_type]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        if source is not None:
            results = [r for r in results if r.source == source]
        return results[-limit:]

    def add_context(
        self,
        record_id: str,
        context_metric: str = "",
        correlation_score: float = 0.0,
        description: str = "",
    ) -> AnomalyContext:
        context = AnomalyContext(
            record_id=record_id,
            context_metric=context_metric,
            correlation_score=correlation_score,
            description=description,
        )
        self._contexts.append(context)
        if len(self._contexts) > self._max_records:
            self._contexts = self._contexts[-self._max_records :]
        logger.info(
            "anomaly_scorer.context_added",
            context_id=context.id,
            record_id=record_id,
            correlation_score=correlation_score,
        )
        return context

    # -- domain operations -----------------------------------------------

    def analyze_anomaly_patterns(self) -> dict[str, Any]:
        """Group by anomaly_type, compute avg anomaly_score and count."""
        groups: dict[str, list[float]] = {}
        for r in self._records:
            groups.setdefault(r.anomaly_type.value, []).append(r.anomaly_score)
        result: dict[str, Any] = {}
        for at, scores in groups.items():
            result[at] = {
                "count": len(scores),
                "avg_anomaly_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_critical_anomalies(self) -> list[dict[str, Any]]:
        """Find records where anomaly_score exceeds min_anomaly_score."""
        critical = [r for r in self._records if r.anomaly_score > self._min_anomaly_score]
        return [
            {
                "record_id": r.id,
                "metric_name": r.metric_name,
                "anomaly_score": r.anomaly_score,
                "anomaly_type": r.anomaly_type.value,
                "severity": r.severity.value,
                "service": r.service,
            }
            for r in critical
        ]

    def rank_by_anomaly_score(self) -> list[dict[str, Any]]:
        """Group by service, compute avg anomaly_score, sort descending."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service, []).append(r.anomaly_score)
        results: list[dict[str, Any]] = []
        for svc, scores in service_scores.items():
            results.append(
                {"service": svc, "avg_anomaly_score": round(sum(scores) / len(scores), 2)}
            )
        results.sort(key=lambda x: x["avg_anomaly_score"], reverse=True)
        return results

    def detect_anomaly_trends(self) -> dict[str, Any]:
        """Split records in half and compute delta in avg anomaly_score; threshold 5.0."""
        if len(self._records) < 2:
            return {"status": "insufficient_data"}
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]
        avg_first = sum(r.anomaly_score for r in first_half) / len(first_half)
        avg_second = sum(r.anomaly_score for r in second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        trend = "worsening" if delta > 5.0 else ("improving" if delta < -5.0 else "stable")
        return {
            "avg_score_first_half": round(avg_first, 2),
            "avg_score_second_half": round(avg_second, 2),
            "delta": delta,
            "trend": trend,
        }

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> MetricAnomalyReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in self._records:
            by_type[r.anomaly_type.value] = by_type.get(r.anomaly_type.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
            by_source[r.source.value] = by_source.get(r.source.value, 0) + 1
        critical_anomalies = sum(1 for r in self._records if r.severity == AnomalySeverity.CRITICAL)
        avg_score = (
            round(
                sum(r.anomaly_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        sorted_records = sorted(self._records, key=lambda r: r.anomaly_score, reverse=True)
        top_anomalies = [r.metric_name for r in sorted_records[:5]]
        recs: list[str] = []
        over_threshold = sum(1 for r in self._records if r.anomaly_score > self._min_anomaly_score)
        if over_threshold > 0:
            recs.append(
                f"{over_threshold} anomaly record(s) exceed the "
                f"{self._min_anomaly_score} score threshold"
            )
        if critical_anomalies > 0:
            recs.append(f"{critical_anomalies} critical anomaly(s) require immediate investigation")
        if not recs:
            recs.append("Metric anomaly scores within acceptable limits")
        return MetricAnomalyReport(
            total_records=len(self._records),
            total_contexts=len(self._contexts),
            critical_anomalies=critical_anomalies,
            avg_anomaly_score=avg_score,
            by_type=by_type,
            by_severity=by_severity,
            by_source=by_source,
            top_anomalies=top_anomalies,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._contexts.clear()
        logger.info("anomaly_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.anomaly_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_contexts": len(self._contexts),
            "min_anomaly_score": self._min_anomaly_score,
            "type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
        }
