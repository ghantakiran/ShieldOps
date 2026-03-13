"""Adaptive Retrieval Strategy Engine —
decide which monitoring tool/data source to query next,
evaluate retrieval efficiency, build retrieval priority map."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DataSource(StrEnum):
    METRICS = "metrics"
    LOGS = "logs"
    TRACES = "traces"
    EVENTS = "events"


class RetrievalStrategy(StrEnum):
    BREADTH_FIRST = "breadth_first"
    DEPTH_FIRST = "depth_first"
    PRIORITY_GUIDED = "priority_guided"
    COST_AWARE = "cost_aware"


class QueryOutcome(StrEnum):
    HIGH_SIGNAL = "high_signal"
    LOW_SIGNAL = "low_signal"
    NO_SIGNAL = "no_signal"
    AMBIGUOUS = "ambiguous"


# --- Models ---


class AdaptiveRetrievalRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    data_source: DataSource = DataSource.METRICS
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.PRIORITY_GUIDED
    query_outcome: QueryOutcome = QueryOutcome.HIGH_SIGNAL
    query_cost_ms: float = 0.0
    signal_score: float = 0.0
    query_text: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AdaptiveRetrievalAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    data_source: DataSource = DataSource.METRICS
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.PRIORITY_GUIDED
    query_outcome: QueryOutcome = QueryOutcome.HIGH_SIGNAL
    efficiency_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AdaptiveRetrievalReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_signal_score: float = 0.0
    by_data_source: dict[str, int] = Field(default_factory=dict)
    by_retrieval_strategy: dict[str, int] = Field(default_factory=dict)
    by_query_outcome: dict[str, int] = Field(default_factory=dict)
    priority_map: dict[str, float] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AdaptiveRetrievalStrategyEngine:
    """Decide which monitoring tool/data source to query next,
    evaluate retrieval efficiency, build retrieval priority map."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AdaptiveRetrievalRecord] = []
        self._analyses: dict[str, AdaptiveRetrievalAnalysis] = {}
        logger.info("adaptive_retrieval_strategy_engine.init", max_records=max_records)

    def add_record(
        self,
        session_id: str = "",
        data_source: DataSource = DataSource.METRICS,
        retrieval_strategy: RetrievalStrategy = RetrievalStrategy.PRIORITY_GUIDED,
        query_outcome: QueryOutcome = QueryOutcome.HIGH_SIGNAL,
        query_cost_ms: float = 0.0,
        signal_score: float = 0.0,
        query_text: str = "",
        description: str = "",
    ) -> AdaptiveRetrievalRecord:
        record = AdaptiveRetrievalRecord(
            session_id=session_id,
            data_source=data_source,
            retrieval_strategy=retrieval_strategy,
            query_outcome=query_outcome,
            query_cost_ms=query_cost_ms,
            signal_score=signal_score,
            query_text=query_text,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "adaptive_retrieval.record_added",
            record_id=record.id,
            session_id=session_id,
        )
        return record

    def process(self, key: str) -> AdaptiveRetrievalAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        eff = round(rec.signal_score / max(rec.query_cost_ms, 1.0) * 1000, 4)
        analysis = AdaptiveRetrievalAnalysis(
            session_id=rec.session_id,
            data_source=rec.data_source,
            retrieval_strategy=rec.retrieval_strategy,
            query_outcome=rec.query_outcome,
            efficiency_score=eff,
            description=(
                f"Session {rec.session_id} source={rec.data_source.value} "
                f"outcome={rec.query_outcome.value}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AdaptiveRetrievalReport:
        by_ds: dict[str, int] = {}
        by_rs: dict[str, int] = {}
        by_qo: dict[str, int] = {}
        scores: list[float] = []
        source_signals: dict[str, list[float]] = {}
        for r in self._records:
            k = r.data_source.value
            by_ds[k] = by_ds.get(k, 0) + 1
            k2 = r.retrieval_strategy.value
            by_rs[k2] = by_rs.get(k2, 0) + 1
            k3 = r.query_outcome.value
            by_qo[k3] = by_qo.get(k3, 0) + 1
            scores.append(r.signal_score)
            source_signals.setdefault(r.data_source.value, []).append(r.signal_score)
        avg_sig = round(sum(scores) / len(scores), 4) if scores else 0.0
        priority_map: dict[str, float] = {
            src: round(sum(sigs) / len(sigs), 4) for src, sigs in source_signals.items()
        }
        recs: list[str] = []
        no_sig = by_qo.get("no_signal", 0)
        if no_sig:
            recs.append(f"{no_sig} queries yielded no signal — adjust data source priority")
        amb = by_qo.get("ambiguous", 0)
        if amb:
            recs.append(f"{amb} ambiguous query outcomes need follow-up")
        if not recs:
            recs.append("Retrieval strategy is performing well")
        return AdaptiveRetrievalReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_signal_score=avg_sig,
            by_data_source=by_ds,
            by_retrieval_strategy=by_rs,
            by_query_outcome=by_qo,
            priority_map=priority_map,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.data_source.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "data_source_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("adaptive_retrieval_strategy_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def select_next_data_source(self) -> list[dict[str, Any]]:
        """Select next data source to query based on signal history."""
        source_stats: dict[str, dict[str, float]] = {}
        for r in self._records:
            dv = r.data_source.value
            source_stats.setdefault(dv, {"total_signal": 0.0, "count": 0.0, "cost": 0.0})
            source_stats[dv]["total_signal"] += r.signal_score
            source_stats[dv]["count"] += 1.0
            source_stats[dv]["cost"] += r.query_cost_ms
        results: list[dict[str, Any]] = []
        for src, stats in source_stats.items():
            avg_sig = stats["total_signal"] / stats["count"]
            avg_cost = stats["cost"] / stats["count"]
            priority = round(avg_sig / max(avg_cost, 1.0) * 1000, 4)
            results.append(
                {
                    "data_source": src,
                    "avg_signal_score": round(avg_sig, 4),
                    "avg_cost_ms": round(avg_cost, 4),
                    "priority_score": priority,
                    "sample_count": int(stats["count"]),
                }
            )
        results.sort(key=lambda x: x["priority_score"], reverse=True)
        return results

    def evaluate_retrieval_efficiency(self) -> list[dict[str, Any]]:
        """Evaluate retrieval efficiency per strategy."""
        strategy_data: dict[str, dict[str, float]] = {}
        for r in self._records:
            sv = r.retrieval_strategy.value
            strategy_data.setdefault(sv, {"signal": 0.0, "cost": 0.0, "count": 0.0})
            strategy_data[sv]["signal"] += r.signal_score
            strategy_data[sv]["cost"] += max(r.query_cost_ms, 1.0)
            strategy_data[sv]["count"] += 1.0
        results: list[dict[str, Any]] = []
        for sv, sd in strategy_data.items():
            eff = round((sd["signal"] / sd["cost"]) * 1000, 4)
            results.append(
                {
                    "strategy": sv,
                    "efficiency_score": eff,
                    "avg_signal": round(sd["signal"] / sd["count"], 4),
                    "total_queries": int(sd["count"]),
                }
            )
        results.sort(key=lambda x: x["efficiency_score"], reverse=True)
        return results

    def build_retrieval_priority_map(self) -> dict[str, Any]:
        """Build a priority map of data sources for future queries."""
        source_scores: dict[str, list[float]] = {}
        source_outcomes: dict[str, dict[str, int]] = {}
        for r in self._records:
            dv = r.data_source.value
            source_scores.setdefault(dv, []).append(r.signal_score)
            source_outcomes.setdefault(dv, {})
            ov = r.query_outcome.value
            source_outcomes[dv][ov] = source_outcomes[dv].get(ov, 0) + 1
        priority_map: dict[str, Any] = {}
        for src, sig_list in source_scores.items():
            avg_sig = sum(sig_list) / len(sig_list)
            priority_map[src] = {
                "avg_signal": round(avg_sig, 4),
                "sample_count": len(sig_list),
                "outcome_distribution": source_outcomes.get(src, {}),
                "priority_rank": 0,
            }
        ranked = sorted(
            priority_map,
            key=lambda x: priority_map[x]["avg_signal"],
            reverse=True,
        )
        for i, src in enumerate(ranked, 1):
            priority_map[src]["priority_rank"] = i
        return priority_map
