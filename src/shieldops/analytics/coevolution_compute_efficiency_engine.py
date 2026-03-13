"""Coevolution Compute Efficiency Engine —
measures compute efficiency of co-evolution (HRPO vs GRPO comparison)."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GroupingStrategy(StrEnum):
    HOP_GROUPED = "hop_grouped"
    RANDOM_GROUPED = "random_grouped"
    UNGROUPED = "ungrouped"
    ADAPTIVE_GROUPED = "adaptive_grouped"


class BatchConfiguration(StrEnum):
    SMALL_BATCH = "small_batch"
    MEDIUM_BATCH = "medium_batch"
    LARGE_BATCH = "large_batch"
    DYNAMIC_BATCH = "dynamic_batch"


class EfficiencyMetric(StrEnum):
    THROUGHPUT = "throughput"
    LATENCY = "latency"
    COST_PER_SAMPLE = "cost_per_sample"
    MEMORY_USAGE = "memory_usage"


# --- Models ---


class ComputeEfficiencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    grouping: GroupingStrategy = GroupingStrategy.HOP_GROUPED
    batch_config: BatchConfiguration = BatchConfiguration.MEDIUM_BATCH
    metric: EfficiencyMetric = EfficiencyMetric.THROUGHPUT
    throughput: float = 0.0
    latency_ms: float = 0.0
    cost_per_sample: float = 0.0
    memory_gb: float = 0.0
    speedup_ratio: float = 1.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ComputeEfficiencyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    avg_throughput: float = 0.0
    avg_latency_ms: float = 0.0
    best_grouping: GroupingStrategy = GroupingStrategy.HOP_GROUPED
    speedup_ratio: float = 1.0
    record_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ComputeEfficiencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_throughput: float = 0.0
    by_grouping: dict[str, int] = Field(default_factory=dict)
    by_batch_config: dict[str, int] = Field(default_factory=dict)
    by_metric: dict[str, int] = Field(default_factory=dict)
    top_experiments: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CoevolutionComputeEfficiencyEngine:
    """Measures compute efficiency of co-evolution (HRPO vs GRPO comparison)."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ComputeEfficiencyRecord] = []
        self._analyses: dict[str, ComputeEfficiencyAnalysis] = {}
        logger.info(
            "coevolution_compute_efficiency_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        experiment_id: str = "",
        grouping: GroupingStrategy = GroupingStrategy.HOP_GROUPED,
        batch_config: BatchConfiguration = BatchConfiguration.MEDIUM_BATCH,
        metric: EfficiencyMetric = EfficiencyMetric.THROUGHPUT,
        throughput: float = 0.0,
        latency_ms: float = 0.0,
        cost_per_sample: float = 0.0,
        memory_gb: float = 0.0,
        speedup_ratio: float = 1.0,
        description: str = "",
    ) -> ComputeEfficiencyRecord:
        record = ComputeEfficiencyRecord(
            experiment_id=experiment_id,
            grouping=grouping,
            batch_config=batch_config,
            metric=metric,
            throughput=throughput,
            latency_ms=latency_ms,
            cost_per_sample=cost_per_sample,
            memory_gb=memory_gb,
            speedup_ratio=speedup_ratio,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "coevolution_compute_efficiency.record_added",
            record_id=record.id,
            experiment_id=experiment_id,
        )
        return record

    def process(self, key: str) -> ComputeEfficiencyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        exp_recs = [r for r in self._records if r.experiment_id == rec.experiment_id]
        throughputs = [r.throughput for r in exp_recs]
        latencies = [r.latency_ms for r in exp_recs]
        speedups = [r.speedup_ratio for r in exp_recs]
        avg_tp = round(sum(throughputs) / len(throughputs), 4) if throughputs else 0.0
        avg_lat = round(sum(latencies) / len(latencies), 4) if latencies else 0.0
        avg_speedup = round(sum(speedups) / len(speedups), 4) if speedups else 1.0
        group_counts: dict[str, int] = {}
        for er in exp_recs:
            gk = er.grouping.value
            group_counts[gk] = group_counts.get(gk, 0) + 1
        best_group_str = max(group_counts, key=lambda x: group_counts[x]) if group_counts else ""
        best_group = GroupingStrategy(best_group_str) if best_group_str else rec.grouping
        analysis = ComputeEfficiencyAnalysis(
            experiment_id=rec.experiment_id,
            avg_throughput=avg_tp,
            avg_latency_ms=avg_lat,
            best_grouping=best_group,
            speedup_ratio=avg_speedup,
            record_count=len(exp_recs),
            description=f"Experiment {rec.experiment_id} throughput {avg_tp}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ComputeEfficiencyReport:
        by_g: dict[str, int] = {}
        by_b: dict[str, int] = {}
        by_m: dict[str, int] = {}
        tps: list[float] = []
        for r in self._records:
            k1 = r.grouping.value
            by_g[k1] = by_g.get(k1, 0) + 1
            k2 = r.batch_config.value
            by_b[k2] = by_b.get(k2, 0) + 1
            k3 = r.metric.value
            by_m[k3] = by_m.get(k3, 0) + 1
            tps.append(r.throughput)
        avg_tp = round(sum(tps) / len(tps), 4) if tps else 0.0
        exp_tp: dict[str, float] = {}
        for r in self._records:
            if r.throughput > exp_tp.get(r.experiment_id, -1.0):
                exp_tp[r.experiment_id] = r.throughput
        top_experiments = sorted(
            exp_tp,
            key=lambda x: exp_tp[x],
            reverse=True,
        )[:10]
        recs_list: list[str] = []
        ungrouped = by_g.get("ungrouped", 0)
        if ungrouped > len(self._records) * 0.5:
            recs_list.append("Majority ungrouped — switch to hop_grouped for HRPO gains")
        if avg_tp < 10.0:
            recs_list.append("Low throughput — consider large_batch configuration")
        if not recs_list:
            recs_list.append("Compute efficiency is well-optimized")
        return ComputeEfficiencyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_throughput=avg_tp,
            by_grouping=by_g,
            by_batch_config=by_b,
            by_metric=by_m,
            top_experiments=top_experiments,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        grouping_dist: dict[str, int] = {}
        for r in self._records:
            k = r.grouping.value
            grouping_dist[k] = grouping_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "grouping_distribution": grouping_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("coevolution_compute_efficiency_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def benchmark_grouping_strategies(self) -> list[dict[str, Any]]:
        """Benchmark throughput and latency across grouping strategies."""
        strategy_data: dict[str, dict[str, list[float]]] = {}
        for r in self._records:
            gk = r.grouping.value
            if gk not in strategy_data:
                strategy_data[gk] = {"throughput": [], "latency": [], "speedup": []}
            strategy_data[gk]["throughput"].append(r.throughput)
            strategy_data[gk]["latency"].append(r.latency_ms)
            strategy_data[gk]["speedup"].append(r.speedup_ratio)
        results: list[dict[str, Any]] = []
        for strategy, data in strategy_data.items():
            tps = data["throughput"]
            lats = data["latency"]
            speedups = data["speedup"]
            avg_tp = round(sum(tps) / len(tps), 4) if tps else 0.0
            avg_lat = round(sum(lats) / len(lats), 4) if lats else 0.0
            avg_speedup = round(sum(speedups) / len(speedups), 4) if speedups else 1.0
            results.append(
                {
                    "grouping_strategy": strategy,
                    "avg_throughput": avg_tp,
                    "avg_latency_ms": avg_lat,
                    "avg_speedup_ratio": avg_speedup,
                    "sample_count": len(tps),
                }
            )
        results.sort(key=lambda x: x["avg_throughput"], reverse=True)
        return results

    def compute_speedup_ratio(
        self,
        baseline_strategy: GroupingStrategy = GroupingStrategy.UNGROUPED,
    ) -> dict[str, Any]:
        """Compute speedup ratio of each strategy vs baseline."""
        strategy_tps: dict[str, list[float]] = {}
        for r in self._records:
            gk = r.grouping.value
            strategy_tps.setdefault(gk, []).append(r.throughput)
        baseline_key = baseline_strategy.value
        baseline_tps = strategy_tps.get(baseline_key, [])
        baseline_avg = sum(baseline_tps) / len(baseline_tps) if baseline_tps else 1.0
        speedups: dict[str, float] = {}
        for strategy, tps in strategy_tps.items():
            avg_tp = sum(tps) / len(tps) if tps else 0.0
            speedups[strategy] = round(avg_tp / baseline_avg, 4) if baseline_avg > 0 else 1.0
        return {
            "baseline_strategy": baseline_key,
            "baseline_avg_throughput": round(baseline_avg, 4),
            "speedup_ratios": speedups,
        }

    def optimize_batch_size(self) -> dict[str, Any]:
        """Recommend optimal batch size based on throughput vs memory trade-off."""
        batch_data: dict[str, dict[str, list[float]]] = {}
        for r in self._records:
            bk = r.batch_config.value
            if bk not in batch_data:
                batch_data[bk] = {"throughput": [], "memory": [], "cost": []}
            batch_data[bk]["throughput"].append(r.throughput)
            batch_data[bk]["memory"].append(r.memory_gb)
            batch_data[bk]["cost"].append(r.cost_per_sample)
        scored: list[dict[str, Any]] = []
        for config, data in batch_data.items():
            tps = data["throughput"]
            mems = data["memory"]
            costs = data["cost"]
            avg_tp = sum(tps) / len(tps) if tps else 0.0
            avg_mem = sum(mems) / len(mems) if mems else 0.0
            avg_cost = sum(costs) / len(costs) if costs else 0.0
            efficiency = round(avg_tp / (avg_mem + 1.0), 4)
            scored.append(
                {
                    "batch_config": config,
                    "avg_throughput": round(avg_tp, 4),
                    "avg_memory_gb": round(avg_mem, 4),
                    "avg_cost_per_sample": round(avg_cost, 4),
                    "efficiency_score": efficiency,
                }
            )
        scored.sort(key=lambda x: x["efficiency_score"], reverse=True)
        recommended = scored[0]["batch_config"] if scored else BatchConfiguration.MEDIUM_BATCH.value
        return {
            "recommended_batch_config": recommended,
            "batch_rankings": scored,
        }
