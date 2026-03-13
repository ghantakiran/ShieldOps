"""Pubsub Optimization Intelligence —
optimize partition distribution, detect hot
partitions, rank topics by rebalancing need."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PartitionStrategy(StrEnum):
    KEY_BASED = "key_based"
    ROUND_ROBIN = "round_robin"
    CUSTOM = "custom"
    HASH = "hash"


class DistributionHealth(StrEnum):
    BALANCED = "balanced"
    SKEWED = "skewed"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class OptimizationAction(StrEnum):
    REBALANCE = "rebalance"
    SPLIT = "split"
    MERGE = "merge"
    MAINTAIN = "maintain"


# --- Models ---


class PubsubOptRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic_name: str = ""
    partition_strategy: PartitionStrategy = PartitionStrategy.KEY_BASED
    distribution_health: DistributionHealth = DistributionHealth.BALANCED
    optimization_action: OptimizationAction = OptimizationAction.MAINTAIN
    partition_count: int = 0
    skew_ratio: float = 0.0
    throughput: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PubsubOptAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic_name: str = ""
    partition_strategy: PartitionStrategy = PartitionStrategy.KEY_BASED
    distribution_score: float = 0.0
    hot_partition_count: int = 0
    rebalance_priority: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PubsubOptReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_skew_ratio: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    skewed_topics: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class PubsubOptimizationIntelligence:
    """Optimize partition distribution, detect hot
    partitions, rank topics by rebalancing need."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[PubsubOptRecord] = []
        self._analyses: dict[str, PubsubOptAnalysis] = {}
        logger.info(
            "pubsub_optimization_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        topic_name: str = "",
        partition_strategy: PartitionStrategy = (PartitionStrategy.KEY_BASED),
        distribution_health: DistributionHealth = (DistributionHealth.BALANCED),
        optimization_action: OptimizationAction = (OptimizationAction.MAINTAIN),
        partition_count: int = 0,
        skew_ratio: float = 0.0,
        throughput: float = 0.0,
        description: str = "",
    ) -> PubsubOptRecord:
        record = PubsubOptRecord(
            topic_name=topic_name,
            partition_strategy=partition_strategy,
            distribution_health=distribution_health,
            optimization_action=optimization_action,
            partition_count=partition_count,
            skew_ratio=skew_ratio,
            throughput=throughput,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "pubsub_opt.record_added",
            record_id=record.id,
            topic_name=topic_name,
        )
        return record

    def process(self, key: str) -> PubsubOptAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        dist_score = round(100.0 - rec.skew_ratio * 100, 2)
        hot_ct = 1 if rec.skew_ratio > 0.5 else 0
        priority = round(
            rec.skew_ratio * 50 + rec.partition_count * 0.1,
            2,
        )
        analysis = PubsubOptAnalysis(
            topic_name=rec.topic_name,
            partition_strategy=rec.partition_strategy,
            distribution_score=dist_score,
            hot_partition_count=hot_ct,
            rebalance_priority=priority,
            description=(f"Topic {rec.topic_name} score {dist_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> PubsubOptReport:
        by_str: dict[str, int] = {}
        by_hlt: dict[str, int] = {}
        by_act: dict[str, int] = {}
        skews: list[float] = []
        for r in self._records:
            k = r.partition_strategy.value
            by_str[k] = by_str.get(k, 0) + 1
            k2 = r.distribution_health.value
            by_hlt[k2] = by_hlt.get(k2, 0) + 1
            k3 = r.optimization_action.value
            by_act[k3] = by_act.get(k3, 0) + 1
            skews.append(r.skew_ratio)
        avg = round(sum(skews) / len(skews), 2) if skews else 0.0
        skewed = list(
            {
                r.topic_name
                for r in self._records
                if r.distribution_health
                in (
                    DistributionHealth.SKEWED,
                    DistributionHealth.CRITICAL,
                )
            }
        )[:10]
        recs: list[str] = []
        if skewed:
            recs.append(f"{len(skewed)} skewed topics detected")
        if not recs:
            recs.append("Partition distribution healthy")
        return PubsubOptReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_skew_ratio=avg,
            by_strategy=by_str,
            by_health=by_hlt,
            by_action=by_act,
            skewed_topics=skewed,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        str_dist: dict[str, int] = {}
        for r in self._records:
            k = r.partition_strategy.value
            str_dist[k] = str_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "strategy_distribution": str_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("pubsub_optimization_intelligence.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def optimize_partition_distribution(
        self,
    ) -> list[dict[str, Any]]:
        """Optimize partition distribution per topic."""
        topic_data: dict[str, list[float]] = {}
        topic_parts: dict[str, int] = {}
        for r in self._records:
            topic_data.setdefault(r.topic_name, []).append(r.skew_ratio)
            topic_parts[r.topic_name] = max(
                topic_parts.get(r.topic_name, 0),
                r.partition_count,
            )
        results: list[dict[str, Any]] = []
        for tn, skews in topic_data.items():
            avg_skew = round(sum(skews) / len(skews), 4)
            action = "rebalance" if avg_skew > 0.3 else "maintain"
            results.append(
                {
                    "topic_name": tn,
                    "avg_skew": avg_skew,
                    "partitions": topic_parts[tn],
                    "action": action,
                    "samples": len(skews),
                }
            )
        results.sort(
            key=lambda x: x["avg_skew"],
            reverse=True,
        )
        return results

    def detect_hot_partitions(
        self,
    ) -> list[dict[str, Any]]:
        """Detect topics with hot partitions."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.skew_ratio > 0.5 and r.topic_name not in seen:
                seen.add(r.topic_name)
                results.append(
                    {
                        "topic_name": r.topic_name,
                        "skew_ratio": r.skew_ratio,
                        "partitions": (r.partition_count),
                        "throughput": r.throughput,
                        "strategy": (r.partition_strategy.value),
                    }
                )
        results.sort(
            key=lambda x: x["skew_ratio"],
            reverse=True,
        )
        return results

    def rank_topics_by_rebalancing_need(
        self,
    ) -> list[dict[str, Any]]:
        """Rank topics by rebalancing need."""
        topic_scores: dict[str, float] = {}
        for r in self._records:
            score = r.skew_ratio * 50 + r.partition_count * 0.1
            topic_scores[r.topic_name] = topic_scores.get(r.topic_name, 0.0) + score
        results: list[dict[str, Any]] = []
        for tn, score in topic_scores.items():
            results.append(
                {
                    "topic_name": tn,
                    "rebalance_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["rebalance_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
