"""Agent Transfer Learning Engine —
evaluate domain similarity, measure transfer effectiveness,
and rank transfer candidates across agent domains."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TransferType(StrEnum):
    DIRECT = "direct"
    FINE_TUNED = "fine_tuned"
    ADAPTED = "adapted"
    ZERO_SHOT = "zero_shot"


class DomainSimilarity(StrEnum):
    IDENTICAL = "identical"
    SIMILAR = "similar"
    RELATED = "related"
    DISTANT = "distant"


class TransferOutcome(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    CATASTROPHIC = "catastrophic"


# --- Models ---


class TransferLearningRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent: str = ""
    target_agent: str = ""
    transfer_type: TransferType = TransferType.FINE_TUNED
    domain_similarity: DomainSimilarity = DomainSimilarity.SIMILAR
    outcome: TransferOutcome = TransferOutcome.POSITIVE
    performance_delta: float = 0.0
    convergence_speed: float = 0.0
    knowledge_retained: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TransferLearningAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent: str = ""
    target_agent: str = ""
    avg_performance_delta: float = 0.0
    dominant_transfer_type: TransferType = TransferType.FINE_TUNED
    dominant_outcome: TransferOutcome = TransferOutcome.POSITIVE
    transfer_count: int = 0
    effectiveness_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TransferLearningReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_performance_delta: float = 0.0
    by_transfer_type: dict[str, int] = Field(default_factory=dict)
    by_domain_similarity: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    top_source_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentTransferLearningEngine:
    """Transfer knowledge between agent domains, evaluate
    domain similarity, and rank transfer candidates."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TransferLearningRecord] = []
        self._analyses: dict[str, TransferLearningAnalysis] = {}
        logger.info(
            "agent_transfer_learning.init",
            max_records=max_records,
        )

    def add_record(
        self,
        source_agent: str = "",
        target_agent: str = "",
        transfer_type: TransferType = TransferType.FINE_TUNED,
        domain_similarity: DomainSimilarity = DomainSimilarity.SIMILAR,
        outcome: TransferOutcome = TransferOutcome.POSITIVE,
        performance_delta: float = 0.0,
        convergence_speed: float = 0.0,
        knowledge_retained: float = 0.0,
        description: str = "",
    ) -> TransferLearningRecord:
        record = TransferLearningRecord(
            source_agent=source_agent,
            target_agent=target_agent,
            transfer_type=transfer_type,
            domain_similarity=domain_similarity,
            outcome=outcome,
            performance_delta=performance_delta,
            convergence_speed=convergence_speed,
            knowledge_retained=knowledge_retained,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "transfer_learning.record_added",
            record_id=record.id,
            source_agent=source_agent,
        )
        return record

    def process(self, key: str) -> TransferLearningAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        pair_recs = [
            r
            for r in self._records
            if r.source_agent == rec.source_agent and r.target_agent == rec.target_agent
        ]
        deltas = [r.performance_delta for r in pair_recs]
        avg_delta = round(sum(deltas) / len(deltas), 2) if deltas else 0.0
        type_counts: dict[str, int] = {}
        outcome_counts: dict[str, int] = {}
        for r in pair_recs:
            type_counts[r.transfer_type.value] = type_counts.get(r.transfer_type.value, 0) + 1
            outcome_counts[r.outcome.value] = outcome_counts.get(r.outcome.value, 0) + 1
        dominant_type = (
            TransferType(max(type_counts, key=lambda x: type_counts[x]))
            if type_counts
            else TransferType.FINE_TUNED
        )
        dominant_outcome = (
            TransferOutcome(max(outcome_counts, key=lambda x: outcome_counts[x]))
            if outcome_counts
            else TransferOutcome.POSITIVE
        )
        effectiveness = round(max(0.0, 50.0 + avg_delta * 50), 2)
        analysis = TransferLearningAnalysis(
            source_agent=rec.source_agent,
            target_agent=rec.target_agent,
            avg_performance_delta=avg_delta,
            dominant_transfer_type=dominant_type,
            dominant_outcome=dominant_outcome,
            transfer_count=len(pair_recs),
            effectiveness_score=effectiveness,
            description=(f"Transfer {rec.source_agent}->{rec.target_agent} delta {avg_delta}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TransferLearningReport:
        by_tt: dict[str, int] = {}
        by_ds: dict[str, int] = {}
        by_oc: dict[str, int] = {}
        deltas: list[float] = []
        for r in self._records:
            by_tt[r.transfer_type.value] = by_tt.get(r.transfer_type.value, 0) + 1
            by_ds[r.domain_similarity.value] = by_ds.get(r.domain_similarity.value, 0) + 1
            by_oc[r.outcome.value] = by_oc.get(r.outcome.value, 0) + 1
            deltas.append(r.performance_delta)
        avg = round(sum(deltas) / len(deltas), 2) if deltas else 0.0
        source_totals: dict[str, float] = {}
        for r in self._records:
            source_totals[r.source_agent] = (
                source_totals.get(r.source_agent, 0.0) + r.performance_delta
            )
        ranked = sorted(
            source_totals,
            key=lambda x: source_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        catastrophic = by_oc.get("catastrophic", 0)
        if catastrophic > 0:
            recs.append(f"{catastrophic} catastrophic transfers — add domain checks")
        negative = by_oc.get("negative", 0)
        if negative > 0:
            recs.append(f"{negative} negative transfer outcomes — review domain similarity")
        if not recs:
            recs.append("Transfer learning outcomes are positive")
        return TransferLearningReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_performance_delta=avg,
            by_transfer_type=by_tt,
            by_domain_similarity=by_ds,
            by_outcome=by_oc,
            top_source_agents=ranked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            dist[r.transfer_type.value] = dist.get(r.transfer_type.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "transfer_type_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("agent_transfer_learning.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def evaluate_domain_similarity(self) -> list[dict[str, Any]]:
        """Evaluate domain similarity across all source-target pairs."""
        pair_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            pair_key = f"{r.source_agent}->{r.target_agent}"
            entry = pair_data.setdefault(
                pair_key,
                {"deltas": [], "similarities": [], "outcomes": []},
            )
            entry["deltas"].append(r.performance_delta)
            entry["similarities"].append(r.domain_similarity.value)
            entry["outcomes"].append(r.outcome.value)
        results: list[dict[str, Any]] = []
        similarity_score = {
            "identical": 1.0,
            "similar": 0.75,
            "related": 0.5,
            "distant": 0.25,
        }
        for pair_key, data in pair_data.items():
            avg_delta = (
                round(sum(data["deltas"]) / len(data["deltas"]), 2) if data["deltas"] else 0.0
            )
            dominant_sim = (
                max(
                    set(data["similarities"]),
                    key=lambda x: data["similarities"].count(x),
                )
                if data["similarities"]
                else "similar"
            )
            sim_score = similarity_score.get(dominant_sim, 0.5)
            results.append(
                {
                    "pair": pair_key,
                    "dominant_similarity": dominant_sim,
                    "similarity_score": sim_score,
                    "avg_performance_delta": avg_delta,
                    "transfer_count": len(data["deltas"]),
                }
            )
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results

    def measure_transfer_effectiveness(self) -> list[dict[str, Any]]:
        """Measure effectiveness of transfers by type and outcome."""
        type_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            entry = type_data.setdefault(
                r.transfer_type.value,
                {"deltas": [], "retained": [], "speeds": []},
            )
            entry["deltas"].append(r.performance_delta)
            entry["retained"].append(r.knowledge_retained)
            entry["speeds"].append(r.convergence_speed)
        results: list[dict[str, Any]] = []
        for ttype, data in type_data.items():
            avg_delta = (
                round(sum(data["deltas"]) / len(data["deltas"]), 2) if data["deltas"] else 0.0
            )
            avg_retained = (
                round(sum(data["retained"]) / len(data["retained"]), 2) if data["retained"] else 0.0
            )
            avg_speed = (
                round(sum(data["speeds"]) / len(data["speeds"]), 2) if data["speeds"] else 0.0
            )
            effectiveness = round(avg_delta * 0.4 + avg_retained * 0.4 + avg_speed * 0.2, 2)
            results.append(
                {
                    "transfer_type": ttype,
                    "avg_delta": avg_delta,
                    "avg_knowledge_retained": avg_retained,
                    "avg_convergence_speed": avg_speed,
                    "effectiveness_score": effectiveness,
                    "sample_count": len(data["deltas"]),
                }
            )
        results.sort(key=lambda x: x["effectiveness_score"], reverse=True)
        return results

    def rank_transfer_candidates(self) -> list[dict[str, Any]]:
        """Rank source agents by their value as transfer knowledge donors."""
        source_data: dict[str, list[TransferLearningRecord]] = {}
        for r in self._records:
            source_data.setdefault(r.source_agent, []).append(r)
        results: list[dict[str, Any]] = []
        for src, recs in source_data.items():
            deltas = [r.performance_delta for r in recs]
            retained = [r.knowledge_retained for r in recs]
            positive_count = sum(1 for r in recs if r.outcome == TransferOutcome.POSITIVE)
            avg_delta = round(sum(deltas) / len(deltas), 2) if deltas else 0.0
            avg_retained = round(sum(retained) / len(retained), 2) if retained else 0.0
            candidate_score = round(
                avg_delta * 0.5 + avg_retained * 0.3 + positive_count / len(recs) * 0.2, 2
            )
            results.append(
                {
                    "source_agent": src,
                    "avg_performance_delta": avg_delta,
                    "avg_knowledge_retained": avg_retained,
                    "positive_transfers": positive_count,
                    "candidate_score": candidate_score,
                    "total_transfers": len(recs),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["candidate_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
