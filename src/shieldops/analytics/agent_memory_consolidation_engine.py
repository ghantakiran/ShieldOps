"""Agent Memory Consolidation Engine —
evaluate memory retention, detect knowledge decay,
and optimize consolidation schedules for agents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MemoryType(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    WORKING = "working"


class ConsolidationPhase(StrEnum):
    ENCODING = "encoding"
    STORAGE = "storage"
    RETRIEVAL = "retrieval"
    PRUNING = "pruning"


class RetentionQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    DEGRADED = "degraded"
    LOST = "lost"


# --- Models ---


class MemoryConsolidationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    memory_type: MemoryType = MemoryType.EPISODIC
    phase: ConsolidationPhase = ConsolidationPhase.ENCODING
    retention_quality: RetentionQuality = RetentionQuality.GOOD
    retention_score: float = 0.0
    decay_rate: float = 0.0
    memory_size_mb: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MemoryConsolidationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    avg_retention: float = 0.0
    dominant_memory_type: MemoryType = MemoryType.EPISODIC
    current_phase: ConsolidationPhase = ConsolidationPhase.ENCODING
    avg_decay_rate: float = 0.0
    record_count: int = 0
    consolidation_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MemoryConsolidationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_retention_score: float = 0.0
    by_memory_type: dict[str, int] = Field(default_factory=dict)
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_retention_quality: dict[str, int] = Field(default_factory=dict)
    top_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentMemoryConsolidationEngine:
    """Consolidate agent learning into long-term memory,
    detect knowledge decay, and optimize consolidation schedules."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[MemoryConsolidationRecord] = []
        self._analyses: dict[str, MemoryConsolidationAnalysis] = {}
        logger.info(
            "agent_memory_consolidation.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        memory_type: MemoryType = MemoryType.EPISODIC,
        phase: ConsolidationPhase = ConsolidationPhase.ENCODING,
        retention_quality: RetentionQuality = RetentionQuality.GOOD,
        retention_score: float = 0.0,
        decay_rate: float = 0.0,
        memory_size_mb: float = 0.0,
        description: str = "",
    ) -> MemoryConsolidationRecord:
        record = MemoryConsolidationRecord(
            agent_id=agent_id,
            memory_type=memory_type,
            phase=phase,
            retention_quality=retention_quality,
            retention_score=retention_score,
            decay_rate=decay_rate,
            memory_size_mb=memory_size_mb,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "memory_consolidation.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> MemoryConsolidationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        agent_recs = [r for r in self._records if r.agent_id == rec.agent_id]
        scores = [r.retention_score for r in agent_recs]
        avg_ret = round(sum(scores) / len(scores), 2) if scores else 0.0
        decays = [r.decay_rate for r in agent_recs]
        avg_decay = round(sum(decays) / len(decays), 4) if decays else 0.0
        type_counts: dict[str, int] = {}
        for r in agent_recs:
            type_counts[r.memory_type.value] = type_counts.get(r.memory_type.value, 0) + 1
        dominant_type = (
            MemoryType(max(type_counts, key=lambda x: type_counts[x]))
            if type_counts
            else MemoryType.EPISODIC
        )
        consolidation_score = round(avg_ret * (1.0 - avg_decay), 2)
        analysis = MemoryConsolidationAnalysis(
            agent_id=rec.agent_id,
            avg_retention=avg_ret,
            dominant_memory_type=dominant_type,
            current_phase=rec.phase,
            avg_decay_rate=avg_decay,
            record_count=len(agent_recs),
            consolidation_score=consolidation_score,
            description=f"Agent {rec.agent_id} consolidation {consolidation_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> MemoryConsolidationReport:
        by_mt: dict[str, int] = {}
        by_ph: dict[str, int] = {}
        by_rq: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            by_mt[r.memory_type.value] = by_mt.get(r.memory_type.value, 0) + 1
            by_ph[r.phase.value] = by_ph.get(r.phase.value, 0) + 1
            by_rq[r.retention_quality.value] = by_rq.get(r.retention_quality.value, 0) + 1
            scores.append(r.retention_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        agent_totals: dict[str, float] = {}
        for r in self._records:
            agent_totals[r.agent_id] = agent_totals.get(r.agent_id, 0.0) + r.retention_score
        ranked = sorted(
            agent_totals,
            key=lambda x: agent_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        lost = by_rq.get("lost", 0)
        if lost > 0:
            recs.append(f"{lost} lost memory records — run re-consolidation")
        degraded = by_rq.get("degraded", 0)
        if degraded > 0:
            recs.append(f"{degraded} degraded memories — schedule pruning")
        if not recs:
            recs.append("Memory consolidation health is excellent")
        return MemoryConsolidationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_retention_score=avg,
            by_memory_type=by_mt,
            by_phase=by_ph,
            by_retention_quality=by_rq,
            top_agents=ranked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            dist[r.memory_type.value] = dist.get(r.memory_type.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "memory_type_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("agent_memory_consolidation.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def evaluate_memory_retention(self) -> list[dict[str, Any]]:
        """Evaluate retention quality per agent and memory type."""
        agent_type_data: dict[str, dict[str, list[float]]] = {}
        for r in self._records:
            agent_entry = agent_type_data.setdefault(r.agent_id, {})
            agent_entry.setdefault(r.memory_type.value, []).append(r.retention_score)
        results: list[dict[str, Any]] = []
        for aid, type_scores in agent_type_data.items():
            all_scores: list[float] = []
            per_type: dict[str, float] = {}
            for mtype, scores in type_scores.items():
                avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
                per_type[mtype] = avg_s
                all_scores.extend(scores)
            overall = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0
            results.append(
                {
                    "agent_id": aid,
                    "overall_retention": overall,
                    "per_type_retention": per_type,
                    "record_count": len(all_scores),
                }
            )
        results.sort(key=lambda x: x["overall_retention"], reverse=True)
        return results

    def detect_knowledge_decay(self) -> list[dict[str, Any]]:
        """Detect agents experiencing significant knowledge decay."""
        agent_data: dict[str, list[MemoryConsolidationRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for aid, recs in agent_data.items():
            if len(recs) < 2:
                continue
            decay_vals = [r.decay_rate for r in recs]
            ret_vals = [r.retention_score for r in recs]
            avg_decay = round(sum(decay_vals) / len(decay_vals), 4) if decay_vals else 0.0
            ret_trend = (ret_vals[-1] - ret_vals[0]) if len(ret_vals) > 1 else 0.0
            is_decaying = avg_decay > 0.1 or ret_trend < -0.1
            results.append(
                {
                    "agent_id": aid,
                    "avg_decay_rate": avg_decay,
                    "retention_trend": round(ret_trend, 4),
                    "is_decaying": is_decaying,
                    "severity": "high" if avg_decay > 0.3 else "medium" if is_decaying else "low",
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["avg_decay_rate"], reverse=True)
        return results

    def optimize_consolidation_schedule(self) -> list[dict[str, Any]]:
        """Recommend consolidation schedule for each agent."""
        agent_data: dict[str, list[MemoryConsolidationRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for aid, recs in agent_data.items():
            decay_vals = [r.decay_rate for r in recs]
            sizes = [r.memory_size_mb for r in recs]
            avg_decay = round(sum(decay_vals) / len(decay_vals), 4) if decay_vals else 0.0
            total_size = round(sum(sizes), 2)
            lost_count = sum(1 for r in recs if r.retention_quality == RetentionQuality.LOST)
            consolidation_urgency = round(avg_decay * 0.5 + lost_count / max(len(recs), 1), 2)
            frequency = (
                "daily"
                if consolidation_urgency > 0.5
                else "weekly"
                if consolidation_urgency > 0.2
                else "monthly"
            )
            results.append(
                {
                    "agent_id": aid,
                    "avg_decay_rate": avg_decay,
                    "total_memory_mb": total_size,
                    "lost_records": lost_count,
                    "consolidation_urgency": consolidation_urgency,
                    "recommended_frequency": frequency,
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["consolidation_urgency"], reverse=True)
        return results
