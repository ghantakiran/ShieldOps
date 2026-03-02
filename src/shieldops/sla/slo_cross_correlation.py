"""SLO Cross-Correlation — correlate SLO pairs, detect weak correlations across services."""

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
    POSITIVE = "positive"
    NEGATIVE = "negative"
    CAUSAL = "causal"
    COINCIDENTAL = "coincidental"
    UNKNOWN = "unknown"


class CorrelationStrength(StrEnum):
    VERY_STRONG = "very_strong"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NEGLIGIBLE = "negligible"


class SLOCategory(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    SATURATION = "saturation"


# --- Models ---


class CorrelationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_pair_name: str = ""
    correlation_type: CorrelationType = CorrelationType.POSITIVE
    correlation_strength: CorrelationStrength = CorrelationStrength.VERY_STRONG
    slo_category: SLOCategory = SLOCategory.AVAILABILITY
    correlation_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CorrelationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slo_pair_name: str = ""
    correlation_type: CorrelationType = CorrelationType.POSITIVE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SLOCrossCorrelationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    weak_correlation_count: int = 0
    avg_correlation_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_strength: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_weak: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOCrossCorrelation:
    """Correlate SLO pairs, detect weak correlations across services."""

    def __init__(
        self,
        max_records: int = 200000,
        correlation_strength_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._correlation_strength_threshold = correlation_strength_threshold
        self._records: list[CorrelationRecord] = []
        self._analyses: list[CorrelationAnalysis] = []
        logger.info(
            "slo_cross_correlation.initialized",
            max_records=max_records,
            correlation_strength_threshold=correlation_strength_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_correlation(
        self,
        slo_pair_name: str,
        correlation_type: CorrelationType = CorrelationType.POSITIVE,
        correlation_strength: CorrelationStrength = CorrelationStrength.VERY_STRONG,
        slo_category: SLOCategory = SLOCategory.AVAILABILITY,
        correlation_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CorrelationRecord:
        record = CorrelationRecord(
            slo_pair_name=slo_pair_name,
            correlation_type=correlation_type,
            correlation_strength=correlation_strength,
            slo_category=slo_category,
            correlation_score=correlation_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_cross_correlation.correlation_recorded",
            record_id=record.id,
            slo_pair_name=slo_pair_name,
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

    def add_analysis(
        self,
        slo_pair_name: str,
        correlation_type: CorrelationType = CorrelationType.POSITIVE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CorrelationAnalysis:
        analysis = CorrelationAnalysis(
            slo_pair_name=slo_pair_name,
            correlation_type=correlation_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "slo_cross_correlation.analysis_added",
            slo_pair_name=slo_pair_name,
            correlation_type=correlation_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_correlation_distribution(self) -> dict[str, Any]:
        """Group by correlation_type; return count and avg correlation_score."""
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

    def identify_weak_correlations(self) -> list[dict[str, Any]]:
        """Return records where correlation_score < correlation_strength_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.correlation_score < self._correlation_strength_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "slo_pair_name": r.slo_pair_name,
                        "correlation_type": r.correlation_type.value,
                        "correlation_score": r.correlation_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["correlation_score"])

    def rank_by_correlation(self) -> list[dict[str, Any]]:
        """Group by service, avg correlation_score, sort ascending (weakest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.correlation_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_correlation_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_correlation_score"])
        return results

    def detect_correlation_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> SLOCrossCorrelationReport:
        by_type: dict[str, int] = {}
        by_strength: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_type[r.correlation_type.value] = by_type.get(r.correlation_type.value, 0) + 1
            by_strength[r.correlation_strength.value] = (
                by_strength.get(r.correlation_strength.value, 0) + 1
            )
            by_category[r.slo_category.value] = by_category.get(r.slo_category.value, 0) + 1
        weak_correlation_count = sum(
            1 for r in self._records if r.correlation_score < self._correlation_strength_threshold
        )
        scores = [r.correlation_score for r in self._records]
        avg_correlation_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        weak_list = self.identify_weak_correlations()
        top_weak = [o["slo_pair_name"] for o in weak_list[:5]]
        recs: list[str] = []
        if self._records and weak_correlation_count > 0:
            recs.append(
                f"{weak_correlation_count} correlation(s) below strength threshold "
                f"({self._correlation_strength_threshold})"
            )
        if self._records and avg_correlation_score < self._correlation_strength_threshold:
            recs.append(
                f"Avg correlation score {avg_correlation_score} below threshold "
                f"({self._correlation_strength_threshold})"
            )
        if not recs:
            recs.append("SLO cross-correlation strength levels are healthy")
        return SLOCrossCorrelationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            weak_correlation_count=weak_correlation_count,
            avg_correlation_score=avg_correlation_score,
            by_type=by_type,
            by_strength=by_strength,
            by_category=by_category,
            top_weak=top_weak,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("slo_cross_correlation.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.correlation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "correlation_strength_threshold": self._correlation_strength_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
