"""Metric Collection Optimizer — optimize metric collection efficiency and costs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CollectionStatus(StrEnum):
    OPTIMAL = "optimal"
    REDUNDANT = "redundant"
    STALE = "stale"
    EXPENSIVE = "expensive"
    MISSING = "missing"


class OptimizationStrategy(StrEnum):
    REDUCE_FREQUENCY = "reduce_frequency"
    AGGREGATE = "aggregate"
    DROP_METRIC = "drop_metric"
    TIER_STORAGE = "tier_storage"
    ADD_COLLECTION = "add_collection"


class MetricTier(StrEnum):
    REAL_TIME = "real_time"
    NEAR_REAL_TIME = "near_real_time"
    HOURLY = "hourly"
    DAILY = "daily"
    ARCHIVAL = "archival"


# --- Models ---


class CollectionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    collection_status: CollectionStatus = CollectionStatus.OPTIMAL
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.REDUCE_FREQUENCY
    metric_tier: MetricTier = MetricTier.REAL_TIME
    efficiency_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CollectionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    collection_status: CollectionStatus = CollectionStatus.OPTIMAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MetricCollectionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_efficiency_count: int = 0
    avg_efficiency_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    top_inefficient: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MetricCollectionOptimizer:
    """Optimize metric collection, identify inefficient collections, detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        collection_efficiency_threshold: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._collection_efficiency_threshold = collection_efficiency_threshold
        self._records: list[CollectionRecord] = []
        self._analyses: list[CollectionAnalysis] = []
        logger.info(
            "metric_collection_optimizer.initialized",
            max_records=max_records,
            collection_efficiency_threshold=collection_efficiency_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_collection(
        self,
        metric_name: str,
        collection_status: CollectionStatus = CollectionStatus.OPTIMAL,
        optimization_strategy: OptimizationStrategy = OptimizationStrategy.REDUCE_FREQUENCY,
        metric_tier: MetricTier = MetricTier.REAL_TIME,
        efficiency_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CollectionRecord:
        record = CollectionRecord(
            metric_name=metric_name,
            collection_status=collection_status,
            optimization_strategy=optimization_strategy,
            metric_tier=metric_tier,
            efficiency_score=efficiency_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "metric_collection_optimizer.collection_recorded",
            record_id=record.id,
            metric_name=metric_name,
            collection_status=collection_status.value,
            optimization_strategy=optimization_strategy.value,
        )
        return record

    def get_collection(self, record_id: str) -> CollectionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_collections(
        self,
        collection_status: CollectionStatus | None = None,
        optimization_strategy: OptimizationStrategy | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CollectionRecord]:
        results = list(self._records)
        if collection_status is not None:
            results = [r for r in results if r.collection_status == collection_status]
        if optimization_strategy is not None:
            results = [r for r in results if r.optimization_strategy == optimization_strategy]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        metric_name: str,
        collection_status: CollectionStatus = CollectionStatus.OPTIMAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CollectionAnalysis:
        analysis = CollectionAnalysis(
            metric_name=metric_name,
            collection_status=collection_status,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "metric_collection_optimizer.analysis_added",
            metric_name=metric_name,
            collection_status=collection_status.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_collection_distribution(self) -> dict[str, Any]:
        """Group by collection_status; return count and avg score."""
        status_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.collection_status.value
            status_data.setdefault(key, []).append(r.efficiency_score)
        result: dict[str, Any] = {}
        for status, scores in status_data.items():
            result[status] = {
                "count": len(scores),
                "avg_efficiency_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_inefficient_collections(self) -> list[dict[str, Any]]:
        """Return collections where efficiency_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.efficiency_score < self._collection_efficiency_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "metric_name": r.metric_name,
                        "collection_status": r.collection_status.value,
                        "optimization_strategy": r.optimization_strategy.value,
                        "efficiency_score": r.efficiency_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["efficiency_score"], reverse=False)
        return results

    def rank_by_efficiency(self) -> list[dict[str, Any]]:
        """Group by service, avg efficiency_score, sort asc (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.efficiency_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_efficiency_score": round(sum(scores) / len(scores), 2),
                    "collection_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_efficiency_score"], reverse=False)
        return results

    def detect_collection_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [a.analysis_score for a in self._analyses]
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

    def generate_report(self) -> MetricCollectionReport:
        by_status: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        for r in self._records:
            by_status[r.collection_status.value] = by_status.get(r.collection_status.value, 0) + 1
            by_strategy[r.optimization_strategy.value] = (
                by_strategy.get(r.optimization_strategy.value, 0) + 1
            )
            by_tier[r.metric_tier.value] = by_tier.get(r.metric_tier.value, 0) + 1
        low_efficiency_count = sum(
            1 for r in self._records if r.efficiency_score < self._collection_efficiency_threshold
        )
        avg_efficiency = (
            round(
                sum(r.efficiency_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        low = self.identify_inefficient_collections()
        top_inefficient = [item["metric_name"] for item in low]
        recs: list[str] = []
        if low:
            recs.append(
                f"{len(low)} inefficient collection(s) detected — review optimization strategies"
            )
        high_e = sum(
            1 for r in self._records if r.efficiency_score >= self._collection_efficiency_threshold
        )
        if high_e > 0:
            recs.append(
                f"{high_e} collection(s) above efficiency threshold"
                f" ({self._collection_efficiency_threshold}%)"
            )
        if not recs:
            recs.append("Metric collection efficiency levels are acceptable")
        return MetricCollectionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_efficiency_count=low_efficiency_count,
            avg_efficiency_score=avg_efficiency,
            by_status=by_status,
            by_strategy=by_strategy,
            by_tier=by_tier,
            top_inefficient=top_inefficient,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("metric_collection_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.collection_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "collection_efficiency_threshold": self._collection_efficiency_threshold,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
