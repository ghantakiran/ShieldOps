"""Alert Correlation Profiler — profile alert correlations and patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CorrelationType(StrEnum):
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    SYMPTOMATIC = "symptomatic"
    CASCADING = "cascading"
    COINCIDENTAL = "coincidental"


class CorrelationStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NEGLIGIBLE = "negligible"
    UNKNOWN = "unknown"


class CorrelationScope(StrEnum):
    SAME_SERVICE = "same_service"
    SAME_TEAM = "same_team"
    CROSS_SERVICE = "cross_service"
    INFRASTRUCTURE = "infrastructure"
    PLATFORM = "platform"


# --- Models ---


class CorrelationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = ""
    correlation_type: CorrelationType = CorrelationType.TEMPORAL
    correlation_strength: CorrelationStrength = CorrelationStrength.UNKNOWN
    correlation_scope: CorrelationScope = CorrelationScope.SAME_SERVICE
    correlation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CorrelationMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = ""
    correlation_type: CorrelationType = CorrelationType.TEMPORAL
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertCorrelationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    strong_correlations: int = 0
    avg_correlation_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_strength: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    top_correlated: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertCorrelationProfiler:
    """Profile alert correlations, detect co-occurring alerts."""

    def __init__(
        self,
        max_records: int = 200000,
        min_correlation_score: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._min_correlation_score = min_correlation_score
        self._records: list[CorrelationRecord] = []
        self._metrics: list[CorrelationMetric] = []
        logger.info(
            "alert_correlation_profiler.initialized",
            max_records=max_records,
            min_correlation_score=min_correlation_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_correlation(
        self,
        correlation_id: str,
        correlation_type: CorrelationType = CorrelationType.TEMPORAL,
        correlation_strength: CorrelationStrength = CorrelationStrength.UNKNOWN,
        correlation_scope: CorrelationScope = CorrelationScope.SAME_SERVICE,
        correlation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CorrelationRecord:
        record = CorrelationRecord(
            correlation_id=correlation_id,
            correlation_type=correlation_type,
            correlation_strength=correlation_strength,
            correlation_scope=correlation_scope,
            correlation_score=correlation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_correlation_profiler.correlation_recorded",
            record_id=record.id,
            correlation_id=correlation_id,
            correlation_type=correlation_type.value,
            correlation_strength=correlation_strength.value,
        )
        return record

    def get_correlation(self, record_id: str) -> CorrelationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_correlations(
        self,
        correlation_type: CorrelationType | None = None,
        correlation_strength: CorrelationStrength | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CorrelationRecord]:
        results = list(self._records)
        if correlation_type is not None:
            results = [r for r in results if r.correlation_type == correlation_type]
        if correlation_strength is not None:
            results = [r for r in results if r.correlation_strength == correlation_strength]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        correlation_id: str,
        correlation_type: CorrelationType = CorrelationType.TEMPORAL,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CorrelationMetric:
        metric = CorrelationMetric(
            correlation_id=correlation_id,
            correlation_type=correlation_type,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "alert_correlation_profiler.metric_added",
            correlation_id=correlation_id,
            correlation_type=correlation_type.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_correlation_distribution(self) -> dict[str, Any]:
        """Group by correlation_type; return count and avg score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.correlation_type.value
            type_data.setdefault(key, []).append(r.correlation_score)
        result: dict[str, Any] = {}
        for ctype, scores in type_data.items():
            result[ctype] = {
                "count": len(scores),
                "avg_correlation_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_strong_correlations(self) -> list[dict[str, Any]]:
        """Return correlations where strength is STRONG or MODERATE."""
        strong_strengths = {
            CorrelationStrength.STRONG,
            CorrelationStrength.MODERATE,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.correlation_strength in strong_strengths:
                results.append(
                    {
                        "record_id": r.id,
                        "correlation_id": r.correlation_id,
                        "correlation_type": r.correlation_type.value,
                        "correlation_strength": r.correlation_strength.value,
                        "correlation_score": r.correlation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["correlation_score"], reverse=True)
        return results

    def rank_by_correlation_score(self) -> list[dict[str, Any]]:
        """Group by service, avg correlation_score, sort desc."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.correlation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_correlation_score": round(sum(scores) / len(scores), 2),
                    "correlation_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_correlation_score"], reverse=True)
        return results

    def detect_correlation_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [m.metric_score for m in self._metrics]
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

    def generate_report(self) -> AlertCorrelationReport:
        by_type: dict[str, int] = {}
        by_strength: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_type[r.correlation_type.value] = by_type.get(r.correlation_type.value, 0) + 1
            by_strength[r.correlation_strength.value] = (
                by_strength.get(r.correlation_strength.value, 0) + 1
            )
            by_scope[r.correlation_scope.value] = by_scope.get(r.correlation_scope.value, 0) + 1
        strong_correlations = sum(
            1
            for r in self._records
            if r.correlation_strength in {CorrelationStrength.STRONG, CorrelationStrength.MODERATE}
        )
        avg_corr = (
            round(
                sum(r.correlation_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        strong = self.identify_strong_correlations()
        top_correlated = [s["correlation_id"] for s in strong]
        recs: list[str] = []
        if strong:
            recs.append(f"{len(strong)} strong correlation(s) detected — review alert grouping")
        low_corr = sum(
            1 for r in self._records if r.correlation_score < self._min_correlation_score
        )
        if low_corr > 0:
            recs.append(
                f"{low_corr} correlation(s) below score threshold ({self._min_correlation_score}%)"
            )
        if not recs:
            recs.append("Alert correlation levels are acceptable")
        return AlertCorrelationReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            strong_correlations=strong_correlations,
            avg_correlation_score=avg_corr,
            by_type=by_type,
            by_strength=by_strength,
            by_scope=by_scope,
            top_correlated=top_correlated,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("alert_correlation_profiler.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.correlation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_correlation_score": self._min_correlation_score,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
