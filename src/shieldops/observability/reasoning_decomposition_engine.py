"""Reasoning Decomposition Engine —
decompose complex investigations into sub-queries,
compose sub-results, optimize decomposition strategy."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DecompositionMethod(StrEnum):
    HIERARCHICAL = "hierarchical"
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    HYBRID = "hybrid"


class SubQueryComplexity(StrEnum):
    ATOMIC = "atomic"
    SIMPLE = "simple"
    COMPOUND = "compound"
    RECURSIVE = "recursive"


class CompositionStrategy(StrEnum):
    MERGE = "merge"
    CHAIN = "chain"
    VOTE = "vote"
    WEIGHTED = "weighted"


# --- Models ---


class ReasoningDecompositionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    decomposition_method: DecompositionMethod = DecompositionMethod.HIERARCHICAL
    sub_query_complexity: SubQueryComplexity = SubQueryComplexity.SIMPLE
    composition_strategy: CompositionStrategy = CompositionStrategy.MERGE
    sub_query_count: int = 1
    resolution_score: float = 0.0
    sub_query_text: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReasoningDecompositionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    decomposition_method: DecompositionMethod = DecompositionMethod.HIERARCHICAL
    sub_query_complexity: SubQueryComplexity = SubQueryComplexity.SIMPLE
    composition_strategy: CompositionStrategy = CompositionStrategy.MERGE
    is_optimal: bool = False
    resolution_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ReasoningDecompositionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_resolution_score: float = 0.0
    by_decomposition_method: dict[str, int] = Field(default_factory=dict)
    by_sub_query_complexity: dict[str, int] = Field(default_factory=dict)
    by_composition_strategy: dict[str, int] = Field(default_factory=dict)
    top_investigations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ReasoningDecompositionEngine:
    """Decompose complex investigations into sub-queries,
    compose sub-results, optimize decomposition strategy."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ReasoningDecompositionRecord] = []
        self._analyses: dict[str, ReasoningDecompositionAnalysis] = {}
        logger.info("reasoning_decomposition_engine.init", max_records=max_records)

    def add_record(
        self,
        investigation_id: str = "",
        decomposition_method: DecompositionMethod = DecompositionMethod.HIERARCHICAL,
        sub_query_complexity: SubQueryComplexity = SubQueryComplexity.SIMPLE,
        composition_strategy: CompositionStrategy = CompositionStrategy.MERGE,
        sub_query_count: int = 1,
        resolution_score: float = 0.0,
        sub_query_text: str = "",
        description: str = "",
    ) -> ReasoningDecompositionRecord:
        record = ReasoningDecompositionRecord(
            investigation_id=investigation_id,
            decomposition_method=decomposition_method,
            sub_query_complexity=sub_query_complexity,
            composition_strategy=composition_strategy,
            sub_query_count=sub_query_count,
            resolution_score=resolution_score,
            sub_query_text=sub_query_text,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "reasoning_decomposition.record_added",
            record_id=record.id,
            investigation_id=investigation_id,
        )
        return record

    def process(self, key: str) -> ReasoningDecompositionAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        is_opt = (
            rec.decomposition_method == DecompositionMethod.HYBRID and rec.resolution_score >= 0.8
        )
        analysis = ReasoningDecompositionAnalysis(
            investigation_id=rec.investigation_id,
            decomposition_method=rec.decomposition_method,
            sub_query_complexity=rec.sub_query_complexity,
            composition_strategy=rec.composition_strategy,
            is_optimal=is_opt,
            resolution_score=round(rec.resolution_score, 4),
            description=(
                f"Investigation {rec.investigation_id} "
                f"method={rec.decomposition_method.value} "
                f"sub_queries={rec.sub_query_count}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ReasoningDecompositionReport:
        by_dm: dict[str, int] = {}
        by_sqc: dict[str, int] = {}
        by_cs: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.decomposition_method.value
            by_dm[k] = by_dm.get(k, 0) + 1
            k2 = r.sub_query_complexity.value
            by_sqc[k2] = by_sqc.get(k2, 0) + 1
            k3 = r.composition_strategy.value
            by_cs[k3] = by_cs.get(k3, 0) + 1
            scores.append(r.resolution_score)
        avg_res = round(sum(scores) / len(scores), 4) if scores else 0.0
        top: list[str] = list(
            {r.investigation_id for r in self._records if r.resolution_score >= 0.8}
        )[:10]
        recs: list[str] = []
        recursive = by_sqc.get("recursive", 0)
        if recursive:
            recs.append(f"{recursive} recursive sub-queries may cause depth explosion")
        if not recs:
            recs.append("Decomposition strategy is well-balanced")
        return ReasoningDecompositionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_resolution_score=avg_res,
            by_decomposition_method=by_dm,
            by_sub_query_complexity=by_sqc,
            by_composition_strategy=by_cs,
            top_investigations=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.decomposition_method.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "decomposition_method_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("reasoning_decomposition_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def decompose_investigation(self) -> list[dict[str, Any]]:
        """Decompose investigations by grouping sub-queries per investigation."""
        inv_map: dict[str, list[ReasoningDecompositionRecord]] = {}
        for r in self._records:
            inv_map.setdefault(r.investigation_id, []).append(r)
        results: list[dict[str, Any]] = []
        for inv_id, inv_recs in inv_map.items():
            methods = list({r.decomposition_method.value for r in inv_recs})
            complexities = list({r.sub_query_complexity.value for r in inv_recs})
            total_sub = sum(r.sub_query_count for r in inv_recs)
            avg_res = sum(r.resolution_score for r in inv_recs) / len(inv_recs)
            results.append(
                {
                    "investigation_id": inv_id,
                    "total_sub_queries": total_sub,
                    "avg_resolution_score": round(avg_res, 4),
                    "methods_used": methods,
                    "complexity_levels": complexities,
                }
            )
        results.sort(key=lambda x: x["avg_resolution_score"], reverse=True)
        return results

    def compose_sub_results(self) -> list[dict[str, Any]]:
        """Compose sub-results per investigation using composition strategy."""
        inv_map: dict[str, list[ReasoningDecompositionRecord]] = {}
        for r in self._records:
            inv_map.setdefault(r.investigation_id, []).append(r)
        results: list[dict[str, Any]] = []
        for inv_id, inv_recs in inv_map.items():
            strategy_counts: dict[str, int] = {}
            for r in inv_recs:
                sv = r.composition_strategy.value
                strategy_counts[sv] = strategy_counts.get(sv, 0) + 1
            dominant_strategy = max(strategy_counts, key=lambda x: strategy_counts[x])
            score_list = [r.resolution_score for r in inv_recs]
            if dominant_strategy == "weighted":
                weights = [r.sub_query_count for r in inv_recs]
                total_w = sum(weights)
                composed = (
                    sum(s * w for s, w in zip(score_list, weights, strict=False)) / total_w
                    if total_w > 0
                    else 0.0
                )
            elif dominant_strategy == "vote":
                majority = sum(1 for s in score_list if s >= 0.5) > len(score_list) / 2
                composed = 1.0 if majority else 0.0
            else:
                composed = sum(score_list) / len(score_list)
            results.append(
                {
                    "investigation_id": inv_id,
                    "dominant_strategy": dominant_strategy,
                    "composed_score": round(composed, 4),
                    "sub_query_count": len(inv_recs),
                }
            )
        results.sort(key=lambda x: x["composed_score"], reverse=True)
        return results

    def optimize_decomposition_strategy(self) -> list[dict[str, Any]]:
        """Identify the best-performing decomposition method by resolution score."""
        method_scores: dict[str, list[float]] = {}
        for r in self._records:
            mv = r.decomposition_method.value
            method_scores.setdefault(mv, []).append(r.resolution_score)
        results: list[dict[str, Any]] = []
        for mv, score_list in method_scores.items():
            avg_s = sum(score_list) / len(score_list)
            results.append(
                {
                    "decomposition_method": mv,
                    "avg_resolution_score": round(avg_s, 4),
                    "sample_count": len(score_list),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_resolution_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
