"""Agent Specialization Scoring Engine —
evaluate specialization depth, detect overfitting risk,
and rank specializations by business value."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SpecializationType(StrEnum):
    DOMAIN = "domain"
    TASK = "task"
    SKILL = "skill"
    ROLE = "role"


class SpecializationDepth(StrEnum):
    GENERALIST = "generalist"
    MODERATE = "moderate"
    SPECIALIST = "specialist"
    EXPERT = "expert"


class EffectivenessLevel(StrEnum):
    EXCEPTIONAL = "exceptional"
    PROFICIENT = "proficient"
    DEVELOPING = "developing"
    INEFFECTIVE = "ineffective"


# --- Models ---


class SpecializationScoringRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    specialization_type: SpecializationType = SpecializationType.DOMAIN
    depth: SpecializationDepth = SpecializationDepth.MODERATE
    effectiveness: EffectivenessLevel = EffectivenessLevel.PROFICIENT
    specialization_score: float = 0.0
    generalization_score: float = 0.0
    task_success_rate: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SpecializationScoringAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    avg_specialization: float = 0.0
    avg_generalization: float = 0.0
    dominant_type: SpecializationType = SpecializationType.DOMAIN
    current_depth: SpecializationDepth = SpecializationDepth.MODERATE
    record_count: int = 0
    value_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SpecializationScoringReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_specialization_score: float = 0.0
    by_specialization_type: dict[str, int] = Field(default_factory=dict)
    by_depth: dict[str, int] = Field(default_factory=dict)
    by_effectiveness: dict[str, int] = Field(default_factory=dict)
    top_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentSpecializationScoringEngine:
    """Score agent specialization effectiveness, detect overfitting
    risk, and rank specializations by value."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[SpecializationScoringRecord] = []
        self._analyses: dict[str, SpecializationScoringAnalysis] = {}
        logger.info(
            "agent_specialization_scoring.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        specialization_type: SpecializationType = SpecializationType.DOMAIN,
        depth: SpecializationDepth = SpecializationDepth.MODERATE,
        effectiveness: EffectivenessLevel = EffectivenessLevel.PROFICIENT,
        specialization_score: float = 0.0,
        generalization_score: float = 0.0,
        task_success_rate: float = 0.0,
        description: str = "",
    ) -> SpecializationScoringRecord:
        record = SpecializationScoringRecord(
            agent_id=agent_id,
            specialization_type=specialization_type,
            depth=depth,
            effectiveness=effectiveness,
            specialization_score=specialization_score,
            generalization_score=generalization_score,
            task_success_rate=task_success_rate,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "specialization_scoring.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> SpecializationScoringAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        agent_recs = [r for r in self._records if r.agent_id == rec.agent_id]
        spec_scores = [r.specialization_score for r in agent_recs]
        gen_scores = [r.generalization_score for r in agent_recs]
        avg_spec = round(sum(spec_scores) / len(spec_scores), 2) if spec_scores else 0.0
        avg_gen = round(sum(gen_scores) / len(gen_scores), 2) if gen_scores else 0.0
        type_counts: dict[str, int] = {}
        for r in agent_recs:
            type_counts[r.specialization_type.value] = (
                type_counts.get(r.specialization_type.value, 0) + 1
            )
        dominant_type = (
            SpecializationType(max(type_counts, key=lambda x: type_counts[x]))
            if type_counts
            else SpecializationType.DOMAIN
        )
        value_score = round(avg_spec * 0.6 + avg_gen * 0.4, 2)
        analysis = SpecializationScoringAnalysis(
            agent_id=rec.agent_id,
            avg_specialization=avg_spec,
            avg_generalization=avg_gen,
            dominant_type=dominant_type,
            current_depth=rec.depth,
            record_count=len(agent_recs),
            value_score=value_score,
            description=f"Agent {rec.agent_id} value score {value_score}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> SpecializationScoringReport:
        by_st: dict[str, int] = {}
        by_dp: dict[str, int] = {}
        by_ef: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            by_st[r.specialization_type.value] = by_st.get(r.specialization_type.value, 0) + 1
            by_dp[r.depth.value] = by_dp.get(r.depth.value, 0) + 1
            by_ef[r.effectiveness.value] = by_ef.get(r.effectiveness.value, 0) + 1
            scores.append(r.specialization_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        agent_totals: dict[str, float] = {}
        for r in self._records:
            agent_totals[r.agent_id] = agent_totals.get(r.agent_id, 0.0) + r.specialization_score
        ranked = sorted(
            agent_totals,
            key=lambda x: agent_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        ineffective = by_ef.get("ineffective", 0)
        if ineffective > 0:
            recs.append(f"{ineffective} ineffective specializations — re-evaluate roles")
        if not recs:
            recs.append("Agent specializations are performing well")
        return SpecializationScoringReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_specialization_score=avg,
            by_specialization_type=by_st,
            by_depth=by_dp,
            by_effectiveness=by_ef,
            top_agents=ranked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            dist[r.specialization_type.value] = dist.get(r.specialization_type.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "specialization_type_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("agent_specialization_scoring.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def evaluate_specialization_depth(self) -> list[dict[str, Any]]:
        """Evaluate specialization depth distribution per agent."""
        agent_data: dict[str, list[SpecializationScoringRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        depth_rank = {
            "generalist": 1,
            "moderate": 2,
            "specialist": 3,
            "expert": 4,
        }
        results: list[dict[str, Any]] = []
        for aid, recs in agent_data.items():
            spec_scores = [r.specialization_score for r in recs]
            avg_spec = round(sum(spec_scores) / len(spec_scores), 2) if spec_scores else 0.0
            depth_counts: dict[str, int] = {}
            for r in recs:
                depth_counts[r.depth.value] = depth_counts.get(r.depth.value, 0) + 1
            dominant_depth = (
                max(
                    depth_counts,
                    key=lambda x: depth_counts[x],
                )
                if depth_counts
                else "moderate"
            )
            depth_score = depth_rank.get(dominant_depth, 2)
            results.append(
                {
                    "agent_id": aid,
                    "avg_specialization": avg_spec,
                    "dominant_depth": dominant_depth,
                    "depth_score": depth_score,
                    "depth_distribution": depth_counts,
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["depth_score"], reverse=True)
        return results

    def detect_overfitting_risk(self) -> list[dict[str, Any]]:
        """Detect agents at risk of over-specialization."""
        agent_data: dict[str, list[SpecializationScoringRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for aid, recs in agent_data.items():
            spec_scores = [r.specialization_score for r in recs]
            gen_scores = [r.generalization_score for r in recs]
            avg_spec = round(sum(spec_scores) / len(spec_scores), 2) if spec_scores else 0.0
            avg_gen = round(sum(gen_scores) / len(gen_scores), 2) if gen_scores else 0.0
            gap = round(avg_spec - avg_gen, 2)
            expert_count = sum(1 for r in recs if r.depth == SpecializationDepth.EXPERT)
            expert_ratio = round(expert_count / max(len(recs), 1), 2)
            overfit_risk = gap > 0.3 or expert_ratio > 0.7
            results.append(
                {
                    "agent_id": aid,
                    "avg_specialization": avg_spec,
                    "avg_generalization": avg_gen,
                    "spec_gen_gap": gap,
                    "expert_ratio": expert_ratio,
                    "overfitting_risk": overfit_risk,
                    "risk_level": "high" if gap > 0.5 else "medium" if overfit_risk else "low",
                }
            )
        results.sort(key=lambda x: x["spec_gen_gap"], reverse=True)
        return results

    def rank_specializations_by_value(self) -> list[dict[str, Any]]:
        """Rank specialization types by delivered business value."""
        type_data: dict[str, list[SpecializationScoringRecord]] = {}
        for r in self._records:
            type_data.setdefault(r.specialization_type.value, []).append(r)
        results: list[dict[str, Any]] = []
        for stype, recs in type_data.items():
            success_rates = [r.task_success_rate for r in recs]
            spec_scores = [r.specialization_score for r in recs]
            avg_success = (
                round(sum(success_rates) / len(success_rates), 2) if success_rates else 0.0
            )
            avg_spec = round(sum(spec_scores) / len(spec_scores), 2) if spec_scores else 0.0
            exceptional_count = sum(
                1 for r in recs if r.effectiveness == EffectivenessLevel.EXCEPTIONAL
            )
            value_score = round(avg_success * 0.5 + avg_spec * 0.3 + exceptional_count * 0.2, 2)
            results.append(
                {
                    "specialization_type": stype,
                    "avg_task_success": avg_success,
                    "avg_specialization": avg_spec,
                    "exceptional_count": exceptional_count,
                    "value_score": value_score,
                    "sample_count": len(recs),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["value_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
