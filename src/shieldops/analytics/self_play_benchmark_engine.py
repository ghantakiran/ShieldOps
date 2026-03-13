"""Self Play Benchmark Engine —
benchmarks self-play vs supervised performance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TrainingParadigm(StrEnum):
    SELF_PLAY = "self_play"
    SUPERVISED = "supervised"
    SEMI_SUPERVISED = "semi_supervised"
    HYBRID = "hybrid"


class BenchmarkMetric(StrEnum):
    ACCURACY = "accuracy"
    EFFICIENCY = "efficiency"
    GENERALIZATION = "generalization"
    ROBUSTNESS = "robustness"


class ComparisonOutcome(StrEnum):
    SELF_PLAY_WINS = "self_play_wins"
    SUPERVISED_WINS = "supervised_wins"
    TIE = "tie"
    INCONCLUSIVE = "inconclusive"


# --- Models ---


class BenchmarkRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    benchmark_id: str = ""
    paradigm: TrainingParadigm = TrainingParadigm.SELF_PLAY
    metric: BenchmarkMetric = BenchmarkMetric.ACCURACY
    outcome: ComparisonOutcome = ComparisonOutcome.INCONCLUSIVE
    score: float = 0.0
    baseline_score: float = 0.0
    data_efficiency: float = 0.0
    generalization_gap: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BenchmarkAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    benchmark_id: str = ""
    avg_score: float = 0.0
    best_paradigm: TrainingParadigm = TrainingParadigm.SELF_PLAY
    dominant_outcome: ComparisonOutcome = ComparisonOutcome.INCONCLUSIVE
    record_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BenchmarkReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    by_paradigm: dict[str, int] = Field(default_factory=dict)
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    top_benchmarks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SelfPlayBenchmarkEngine:
    """Benchmarks self-play vs supervised performance."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[BenchmarkRecord] = []
        self._analyses: dict[str, BenchmarkAnalysis] = {}
        logger.info(
            "self_play_benchmark_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        benchmark_id: str = "",
        paradigm: TrainingParadigm = TrainingParadigm.SELF_PLAY,
        metric: BenchmarkMetric = BenchmarkMetric.ACCURACY,
        outcome: ComparisonOutcome = ComparisonOutcome.INCONCLUSIVE,
        score: float = 0.0,
        baseline_score: float = 0.0,
        data_efficiency: float = 0.0,
        generalization_gap: float = 0.0,
        description: str = "",
    ) -> BenchmarkRecord:
        record = BenchmarkRecord(
            benchmark_id=benchmark_id,
            paradigm=paradigm,
            metric=metric,
            outcome=outcome,
            score=score,
            baseline_score=baseline_score,
            data_efficiency=data_efficiency,
            generalization_gap=generalization_gap,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "self_play_benchmark.record_added",
            record_id=record.id,
            benchmark_id=benchmark_id,
        )
        return record

    def process(self, key: str) -> BenchmarkAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        bench_recs = [r for r in self._records if r.benchmark_id == rec.benchmark_id]
        scores = [r.score for r in bench_recs]
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        paradigm_scores: dict[str, float] = {}
        for br in bench_recs:
            pk = br.paradigm.value
            paradigm_scores[pk] = paradigm_scores.get(pk, 0.0) + br.score
        best_paradigm_str = (
            max(paradigm_scores, key=lambda x: paradigm_scores[x]) if paradigm_scores else ""
        )
        best_paradigm = TrainingParadigm(best_paradigm_str) if best_paradigm_str else rec.paradigm
        outcome_counts: dict[str, int] = {}
        for br in bench_recs:
            ok = br.outcome.value
            outcome_counts[ok] = outcome_counts.get(ok, 0) + 1
        dom_outcome_str = (
            max(outcome_counts, key=lambda x: outcome_counts[x]) if outcome_counts else ""
        )
        dom_outcome = ComparisonOutcome(dom_outcome_str) if dom_outcome_str else rec.outcome
        analysis = BenchmarkAnalysis(
            benchmark_id=rec.benchmark_id,
            avg_score=avg_score,
            best_paradigm=best_paradigm,
            dominant_outcome=dom_outcome,
            record_count=len(bench_recs),
            description=f"Benchmark {rec.benchmark_id} avg score {avg_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> BenchmarkReport:
        by_p: dict[str, int] = {}
        by_m: dict[str, int] = {}
        by_o: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k1 = r.paradigm.value
            by_p[k1] = by_p.get(k1, 0) + 1
            k2 = r.metric.value
            by_m[k2] = by_m.get(k2, 0) + 1
            k3 = r.outcome.value
            by_o[k3] = by_o.get(k3, 0) + 1
            scores.append(r.score)
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        bench_scores: dict[str, float] = {}
        for r in self._records:
            if r.score > bench_scores.get(r.benchmark_id, -1.0):
                bench_scores[r.benchmark_id] = r.score
        top_benchmarks = sorted(
            bench_scores,
            key=lambda x: bench_scores[x],
            reverse=True,
        )[:10]
        recs_list: list[str] = []
        supervised_wins = by_o.get("supervised_wins", 0)
        self_play_wins = by_o.get("self_play_wins", 0)
        if supervised_wins > self_play_wins:
            recs_list.append("Supervised outperforming self-play — review reward shaping")
        elif self_play_wins > supervised_wins:
            recs_list.append("Self-play is winning — scale up co-evolution iterations")
        if not recs_list:
            recs_list.append("Self-play and supervised performance are comparable")
        return BenchmarkReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg_score,
            by_paradigm=by_p,
            by_metric=by_m,
            by_outcome=by_o,
            top_benchmarks=top_benchmarks,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        paradigm_dist: dict[str, int] = {}
        for r in self._records:
            k = r.paradigm.value
            paradigm_dist[k] = paradigm_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "paradigm_distribution": paradigm_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("self_play_benchmark_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def run_comparative_benchmark(
        self,
        paradigms: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Run comparative benchmark across training paradigms."""
        paradigm_data: dict[str, dict[str, list[float]]] = {}
        for r in self._records:
            pk = r.paradigm.value
            if paradigms and pk not in paradigms:
                continue
            if pk not in paradigm_data:
                paradigm_data[pk] = {
                    "scores": [],
                    "efficiency": [],
                    "generalization": [],
                }
            paradigm_data[pk]["scores"].append(r.score)
            paradigm_data[pk]["efficiency"].append(r.data_efficiency)
            paradigm_data[pk]["generalization"].append(r.generalization_gap)
        results: list[dict[str, Any]] = []
        for pk, data in paradigm_data.items():
            sc = data["scores"]
            eff = data["efficiency"]
            gen = data["generalization"]
            avg_score = round(sum(sc) / len(sc), 4) if sc else 0.0
            avg_eff = round(sum(eff) / len(eff), 4) if eff else 0.0
            avg_gen = round(sum(gen) / len(gen), 4) if gen else 0.0
            results.append(
                {
                    "paradigm": pk,
                    "avg_score": avg_score,
                    "avg_data_efficiency": avg_eff,
                    "avg_generalization_gap": avg_gen,
                    "sample_count": len(sc),
                }
            )
        results.sort(key=lambda x: x["avg_score"], reverse=True)
        return results

    def measure_generalization_gap(self) -> dict[str, Any]:
        """Measure generalization gap between self-play and supervised."""
        paradigm_gaps: dict[str, list[float]] = {}
        for r in self._records:
            pk = r.paradigm.value
            paradigm_gaps.setdefault(pk, []).append(r.generalization_gap)
        gap_summary: dict[str, float] = {}
        for paradigm, gaps in paradigm_gaps.items():
            gap_summary[paradigm] = round(sum(gaps) / len(gaps), 4) if gaps else 0.0
        sp_gap = gap_summary.get(TrainingParadigm.SELF_PLAY.value, 0.0)
        sup_gap = gap_summary.get(TrainingParadigm.SUPERVISED.value, 0.0)
        relative_gap = round(sp_gap - sup_gap, 4)
        return {
            "paradigm_avg_gaps": gap_summary,
            "self_play_gap": sp_gap,
            "supervised_gap": sup_gap,
            "relative_gap": relative_gap,
            "self_play_generalizes_better": relative_gap < 0,
        }

    def compute_data_efficiency_ratio(self) -> dict[str, Any]:
        """Compute data efficiency ratio of self-play vs supervised."""
        paradigm_eff: dict[str, list[float]] = {}
        for r in self._records:
            pk = r.paradigm.value
            paradigm_eff.setdefault(pk, []).append(r.data_efficiency)
        eff_avgs: dict[str, float] = {}
        for paradigm, effs in paradigm_eff.items():
            eff_avgs[paradigm] = round(sum(effs) / len(effs), 4) if effs else 0.0
        sp_eff = eff_avgs.get(TrainingParadigm.SELF_PLAY.value, 1.0)
        sup_eff = eff_avgs.get(TrainingParadigm.SUPERVISED.value, 1.0)
        ratio = round(sp_eff / sup_eff, 4) if sup_eff > 0 else 0.0
        return {
            "paradigm_efficiencies": eff_avgs,
            "self_play_efficiency": sp_eff,
            "supervised_efficiency": sup_eff,
            "efficiency_ratio": ratio,
            "self_play_more_efficient": ratio > 1.0,
        }
