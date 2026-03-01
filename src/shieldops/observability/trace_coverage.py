"""Trace Coverage Analyzer — measure trace instrumentation coverage."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CoverageLevel(StrEnum):
    FULL = "full"
    HIGH = "high"
    PARTIAL = "partial"
    LOW = "low"
    NONE = "none"


class InstrumentationType(StrEnum):
    AUTO_INSTRUMENTED = "auto_instrumented"
    MANUAL_INSTRUMENTED = "manual_instrumented"
    HYBRID = "hybrid"
    LEGACY = "legacy"
    UNINSTRUMENTED = "uninstrumented"


class CoverageGap(StrEnum):
    MISSING_SPANS = "missing_spans"
    INCOMPLETE_CONTEXT = "incomplete_context"
    NO_ATTRIBUTES = "no_attributes"
    BROKEN_PROPAGATION = "broken_propagation"
    SAMPLING_LOSS = "sampling_loss"


# --- Models ---


class TraceCoverageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    coverage_level: CoverageLevel = CoverageLevel.NONE
    instrumentation_type: InstrumentationType = InstrumentationType.UNINSTRUMENTED
    coverage_gap: CoverageGap = CoverageGap.MISSING_SPANS
    coverage_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CoverageMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    coverage_level: CoverageLevel = CoverageLevel.NONE
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceCoverageReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    low_coverage_count: int = 0
    avg_coverage_score: float = 0.0
    by_coverage_level: dict[str, int] = Field(default_factory=dict)
    by_instrumentation: dict[str, int] = Field(default_factory=dict)
    by_gap: dict[str, int] = Field(default_factory=dict)
    top_uncovered: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TraceCoverageAnalyzer:
    """Measure trace instrumentation coverage, detect uninstrumented services."""

    def __init__(
        self,
        max_records: int = 200000,
        min_coverage_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_coverage_pct = min_coverage_pct
        self._records: list[TraceCoverageRecord] = []
        self._metrics: list[CoverageMetric] = []
        logger.info(
            "trace_coverage.initialized",
            max_records=max_records,
            min_coverage_pct=min_coverage_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_coverage(
        self,
        service_id: str,
        coverage_level: CoverageLevel = CoverageLevel.NONE,
        instrumentation_type: InstrumentationType = InstrumentationType.UNINSTRUMENTED,
        coverage_gap: CoverageGap = CoverageGap.MISSING_SPANS,
        coverage_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TraceCoverageRecord:
        record = TraceCoverageRecord(
            service_id=service_id,
            coverage_level=coverage_level,
            instrumentation_type=instrumentation_type,
            coverage_gap=coverage_gap,
            coverage_score=coverage_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "trace_coverage.coverage_recorded",
            record_id=record.id,
            service_id=service_id,
            coverage_level=coverage_level.value,
            instrumentation_type=instrumentation_type.value,
        )
        return record

    def get_coverage(self, record_id: str) -> TraceCoverageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_coverages(
        self,
        level: CoverageLevel | None = None,
        instrumentation: InstrumentationType | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TraceCoverageRecord]:
        results = list(self._records)
        if level is not None:
            results = [r for r in results if r.coverage_level == level]
        if instrumentation is not None:
            results = [r for r in results if r.instrumentation_type == instrumentation]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        service_id: str,
        coverage_level: CoverageLevel = CoverageLevel.NONE,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CoverageMetric:
        metric = CoverageMetric(
            service_id=service_id,
            coverage_level=coverage_level,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "trace_coverage.metric_added",
            service_id=service_id,
            coverage_level=coverage_level.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_coverage_distribution(self) -> dict[str, Any]:
        """Group by coverage_level; return count and avg coverage_score."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.coverage_level.value
            level_data.setdefault(key, []).append(r.coverage_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_coverage_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_coverage_services(self) -> list[dict[str, Any]]:
        """Return records where coverage_level is LOW or NONE."""
        low_levels = {CoverageLevel.LOW, CoverageLevel.NONE}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_level in low_levels:
                results.append(
                    {
                        "record_id": r.id,
                        "service_id": r.service_id,
                        "coverage_level": r.coverage_level.value,
                        "instrumentation_type": r.instrumentation_type.value,
                        "coverage_gap": r.coverage_gap.value,
                        "coverage_score": r.coverage_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_coverage_score(self) -> list[dict[str, Any]]:
        """Group by service, avg coverage_score, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.coverage_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_coverage_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_score"])
        return results

    def detect_coverage_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
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

    def generate_report(self) -> TraceCoverageReport:
        by_coverage_level: dict[str, int] = {}
        by_instrumentation: dict[str, int] = {}
        by_gap: dict[str, int] = {}
        for r in self._records:
            by_coverage_level[r.coverage_level.value] = (
                by_coverage_level.get(r.coverage_level.value, 0) + 1
            )
            by_instrumentation[r.instrumentation_type.value] = (
                by_instrumentation.get(r.instrumentation_type.value, 0) + 1
            )
            by_gap[r.coverage_gap.value] = by_gap.get(r.coverage_gap.value, 0) + 1
        low_coverage = self.identify_low_coverage_services()
        low_coverage_count = len(low_coverage)
        avg_coverage_score = (
            round(
                sum(r.coverage_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        rankings = self.rank_by_coverage_score()
        top_uncovered = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if low_coverage_count > 0:
            recs.append(
                f"{low_coverage_count} low-coverage service(s) detected — add instrumentation"
            )
        if self._records:
            low_pct = round(low_coverage_count / len(self._records) * 100, 2)
            if low_pct > (100.0 - self._min_coverage_pct):
                recs.append(
                    f"Low-coverage rate {low_pct}% exceeds "
                    f"acceptable threshold ({100.0 - self._min_coverage_pct}%)"
                )
        if not recs:
            recs.append("Trace coverage levels are acceptable")
        return TraceCoverageReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            low_coverage_count=low_coverage_count,
            avg_coverage_score=avg_coverage_score,
            by_coverage_level=by_coverage_level,
            by_instrumentation=by_instrumentation,
            by_gap=by_gap,
            top_uncovered=top_uncovered,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("trace_coverage.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.coverage_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_coverage_pct": self._min_coverage_pct,
            "coverage_level_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
