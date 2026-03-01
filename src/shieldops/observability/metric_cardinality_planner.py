"""Metric Cardinality Planner — plan and manage metric cardinality for cost control."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CardinalityLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


class MetricSource(StrEnum):
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"
    CUSTOM = "custom"
    SYNTHETIC = "synthetic"
    EXTERNAL = "external"


class ReductionStrategy(StrEnum):
    DROP_LABELS = "drop_labels"
    AGGREGATE = "aggregate"
    SAMPLE = "sample"
    ARCHIVE = "archive"
    KEEP = "keep"


# --- Models ---


class CardinalityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    cardinality_level: CardinalityLevel = CardinalityLevel.LOW
    metric_source: MetricSource = MetricSource.APPLICATION
    reduction_strategy: ReductionStrategy = ReductionStrategy.KEEP
    cardinality_count: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CardinalityPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    cardinality_level: CardinalityLevel = CardinalityLevel.LOW
    plan_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MetricCardinalityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_plans: int = 0
    high_cardinality_count: int = 0
    avg_cardinality_count: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    top_high_cardinality: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MetricCardinalityPlanner:
    """Plan and manage metric cardinality to control observability costs."""

    def __init__(
        self,
        max_records: int = 200000,
        max_high_cardinality_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_high_cardinality_pct = max_high_cardinality_pct
        self._records: list[CardinalityRecord] = []
        self._plans: list[CardinalityPlan] = []
        logger.info(
            "metric_cardinality.initialized",
            max_records=max_records,
            max_high_cardinality_pct=max_high_cardinality_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_cardinality(
        self,
        metric_name: str,
        cardinality_level: CardinalityLevel = CardinalityLevel.LOW,
        metric_source: MetricSource = MetricSource.APPLICATION,
        reduction_strategy: ReductionStrategy = ReductionStrategy.KEEP,
        cardinality_count: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CardinalityRecord:
        record = CardinalityRecord(
            metric_name=metric_name,
            cardinality_level=cardinality_level,
            metric_source=metric_source,
            reduction_strategy=reduction_strategy,
            cardinality_count=cardinality_count,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "metric_cardinality.cardinality_recorded",
            record_id=record.id,
            metric_name=metric_name,
            cardinality_level=cardinality_level.value,
            metric_source=metric_source.value,
        )
        return record

    def get_cardinality(self, record_id: str) -> CardinalityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_cardinalities(
        self,
        level: CardinalityLevel | None = None,
        source: MetricSource | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CardinalityRecord]:
        results = list(self._records)
        if level is not None:
            results = [r for r in results if r.cardinality_level == level]
        if source is not None:
            results = [r for r in results if r.metric_source == source]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_plan(
        self,
        metric_name: str,
        cardinality_level: CardinalityLevel = CardinalityLevel.LOW,
        plan_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CardinalityPlan:
        plan = CardinalityPlan(
            metric_name=metric_name,
            cardinality_level=cardinality_level,
            plan_score=plan_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._plans.append(plan)
        if len(self._plans) > self._max_records:
            self._plans = self._plans[-self._max_records :]
        logger.info(
            "metric_cardinality.plan_added",
            metric_name=metric_name,
            cardinality_level=cardinality_level.value,
            plan_score=plan_score,
        )
        return plan

    # -- domain operations --------------------------------------------------

    def analyze_cardinality_distribution(self) -> dict[str, Any]:
        """Group by cardinality_level; return count and avg cardinality_count per level."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.cardinality_level.value
            level_data.setdefault(key, []).append(r.cardinality_count)
        result: dict[str, Any] = {}
        for level, counts in level_data.items():
            result[level] = {
                "count": len(counts),
                "avg_cardinality_count": round(sum(counts) / len(counts), 2),
            }
        return result

    def identify_high_cardinality_metrics(self) -> list[dict[str, Any]]:
        """Return records where cardinality_level is CRITICAL or HIGH."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.cardinality_level in (CardinalityLevel.CRITICAL, CardinalityLevel.HIGH):
                results.append(
                    {
                        "record_id": r.id,
                        "metric_name": r.metric_name,
                        "cardinality_level": r.cardinality_level.value,
                        "cardinality_count": r.cardinality_count,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_cardinality(self) -> list[dict[str, Any]]:
        """Group by service, avg cardinality_count, sort descending."""
        svc_counts: dict[str, list[float]] = {}
        for r in self._records:
            svc_counts.setdefault(r.service, []).append(r.cardinality_count)
        results: list[dict[str, Any]] = []
        for service, counts in svc_counts.items():
            results.append(
                {
                    "service": service,
                    "avg_cardinality_count": round(sum(counts) / len(counts), 2),
                    "metric_count": len(counts),
                }
            )
        results.sort(key=lambda x: x["avg_cardinality_count"], reverse=True)
        return results

    def detect_cardinality_trends(self) -> dict[str, Any]:
        """Split-half comparison on plan_score; delta threshold 5.0."""
        if len(self._plans) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [p.plan_score for p in self._plans]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> MetricCardinalityReport:
        by_level: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_level[r.cardinality_level.value] = by_level.get(r.cardinality_level.value, 0) + 1
            by_source[r.metric_source.value] = by_source.get(r.metric_source.value, 0) + 1
            by_strategy[r.reduction_strategy.value] = (
                by_strategy.get(r.reduction_strategy.value, 0) + 1
            )
        high_cardinality_count = sum(
            1
            for r in self._records
            if r.cardinality_level in (CardinalityLevel.CRITICAL, CardinalityLevel.HIGH)
        )
        avg_cardinality = (
            round(sum(r.cardinality_count for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_cardinality()
        top_high_cardinality = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if high_cardinality_count > 0:
            recs.append(
                f"{high_cardinality_count} high-cardinality metric(s) detected — review labels"
            )
        high_pct = (
            round(high_cardinality_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        if high_pct > self._max_high_cardinality_pct:
            recs.append(
                f"High-cardinality rate {high_pct}% exceeds "
                f"threshold ({self._max_high_cardinality_pct}%)"
            )
        if not recs:
            recs.append("Metric cardinality levels are acceptable")
        return MetricCardinalityReport(
            total_records=len(self._records),
            total_plans=len(self._plans),
            high_cardinality_count=high_cardinality_count,
            avg_cardinality_count=avg_cardinality,
            by_level=by_level,
            by_source=by_source,
            by_strategy=by_strategy,
            top_high_cardinality=top_high_cardinality,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._plans.clear()
        logger.info("metric_cardinality.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.cardinality_level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_plans": len(self._plans),
            "max_high_cardinality_pct": self._max_high_cardinality_pct,
            "level_distribution": level_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
