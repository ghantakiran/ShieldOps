"""Agent Skill Acquisition Engine —
tracks which SRE skills agents acquire at each iteration."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SkillDomain(StrEnum):
    DIAGNOSIS = "diagnosis"
    REMEDIATION = "remediation"
    TRIAGE = "triage"
    PREVENTION = "prevention"


class AcquisitionStatus(StrEnum):
    NOT_STARTED = "not_started"
    LEARNING = "learning"
    ACQUIRED = "acquired"
    MASTERED = "mastered"


class SkillDependency(StrEnum):
    PREREQUISITE = "prerequisite"
    COREQUISITE = "corequisite"
    INDEPENDENT = "independent"
    SEQUENTIAL = "sequential"


# --- Models ---


class SkillAcquisitionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    skill_name: str = ""
    domain: SkillDomain = SkillDomain.DIAGNOSIS
    status: AcquisitionStatus = AcquisitionStatus.NOT_STARTED
    dependency: SkillDependency = SkillDependency.INDEPENDENT
    proficiency_score: float = 0.0
    iteration_acquired: int = 0
    prerequisite_skill: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SkillAcquisitionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    skills_acquired: int = 0
    skills_mastered: int = 0
    avg_proficiency: float = 0.0
    dominant_domain: SkillDomain = SkillDomain.DIAGNOSIS
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SkillAcquisitionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_proficiency: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_dependency: dict[str, int] = Field(default_factory=dict)
    top_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentSkillAcquisitionEngine:
    """Tracks which SRE skills agents acquire at each iteration."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[SkillAcquisitionRecord] = []
        self._analyses: dict[str, SkillAcquisitionAnalysis] = {}
        logger.info(
            "agent_skill_acquisition_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        skill_name: str = "",
        domain: SkillDomain = SkillDomain.DIAGNOSIS,
        status: AcquisitionStatus = AcquisitionStatus.NOT_STARTED,
        dependency: SkillDependency = SkillDependency.INDEPENDENT,
        proficiency_score: float = 0.0,
        iteration_acquired: int = 0,
        prerequisite_skill: str = "",
        description: str = "",
    ) -> SkillAcquisitionRecord:
        record = SkillAcquisitionRecord(
            agent_id=agent_id,
            skill_name=skill_name,
            domain=domain,
            status=status,
            dependency=dependency,
            proficiency_score=proficiency_score,
            iteration_acquired=iteration_acquired,
            prerequisite_skill=prerequisite_skill,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "agent_skill_acquisition.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> SkillAcquisitionAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        agent_recs = [r for r in self._records if r.agent_id == rec.agent_id]
        profs = [r.proficiency_score for r in agent_recs]
        avg_prof = round(sum(profs) / len(profs), 4) if profs else 0.0
        acquired = sum(
            1
            for r in agent_recs
            if r.status in (AcquisitionStatus.ACQUIRED, AcquisitionStatus.MASTERED)
        )
        mastered = sum(1 for r in agent_recs if r.status == AcquisitionStatus.MASTERED)
        domain_counts: dict[str, int] = {}
        for ar in agent_recs:
            dk = ar.domain.value
            domain_counts[dk] = domain_counts.get(dk, 0) + 1
        dom_str = max(domain_counts, key=lambda x: domain_counts[x]) if domain_counts else ""
        dom = SkillDomain(dom_str) if dom_str else rec.domain
        analysis = SkillAcquisitionAnalysis(
            agent_id=rec.agent_id,
            skills_acquired=acquired,
            skills_mastered=mastered,
            avg_proficiency=avg_prof,
            dominant_domain=dom,
            description=f"Agent {rec.agent_id} {acquired} acquired {mastered} mastered",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> SkillAcquisitionReport:
        by_d: dict[str, int] = {}
        by_s: dict[str, int] = {}
        by_dep: dict[str, int] = {}
        profs: list[float] = []
        for r in self._records:
            k1 = r.domain.value
            by_d[k1] = by_d.get(k1, 0) + 1
            k2 = r.status.value
            by_s[k2] = by_s.get(k2, 0) + 1
            k3 = r.dependency.value
            by_dep[k3] = by_dep.get(k3, 0) + 1
            profs.append(r.proficiency_score)
        avg_prof = round(sum(profs) / len(profs), 4) if profs else 0.0
        agent_profs: dict[str, float] = {}
        for r in self._records:
            agent_profs[r.agent_id] = agent_profs.get(r.agent_id, 0.0) + r.proficiency_score
        top_agents = sorted(
            agent_profs,
            key=lambda x: agent_profs[x],
            reverse=True,
        )[:10]
        recs_list: list[str] = []
        not_started = by_s.get("not_started", 0)
        if not_started > len(self._records) * 0.4:
            recs_list.append("High proportion of unstarted skills — prioritize onboarding")
        if not recs_list:
            recs_list.append("Skill acquisition is progressing well")
        return SkillAcquisitionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_proficiency=avg_prof,
            by_domain=by_d,
            by_status=by_s,
            by_dependency=by_dep,
            top_agents=top_agents,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            k = r.domain.value
            domain_dist[k] = domain_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "domain_distribution": domain_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("agent_skill_acquisition_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def map_skill_acquisition_graph(
        self,
        agent_id: str,
    ) -> list[dict[str, Any]]:
        """Map the skill acquisition dependency graph for an agent."""
        agent_recs = [r for r in self._records if r.agent_id == agent_id]
        graph: list[dict[str, Any]] = []
        seen_skills: set[str] = set()
        for r in agent_recs:
            if r.skill_name in seen_skills:
                continue
            seen_skills.add(r.skill_name)
            graph.append(
                {
                    "skill_name": r.skill_name,
                    "domain": r.domain.value,
                    "status": r.status.value,
                    "dependency": r.dependency.value,
                    "prerequisite": r.prerequisite_skill,
                    "proficiency": r.proficiency_score,
                    "iteration_acquired": r.iteration_acquired,
                }
            )
        graph.sort(key=lambda x: x["proficiency"], reverse=True)
        return graph

    def identify_skill_gaps(self, agent_id: str) -> dict[str, Any]:
        """Identify skills that an agent has not yet acquired."""
        agent_recs = [r for r in self._records if r.agent_id == agent_id]
        all_skills: set[str] = {r.skill_name for r in self._records}
        agent_skills: set[str] = {r.skill_name for r in agent_recs}
        gaps = all_skills - agent_skills
        not_started = [
            r.skill_name for r in agent_recs if r.status == AcquisitionStatus.NOT_STARTED
        ]
        learning = [r.skill_name for r in agent_recs if r.status == AcquisitionStatus.LEARNING]
        return {
            "agent_id": agent_id,
            "total_skills": len(all_skills),
            "agent_skills": len(agent_skills),
            "missing_skills": sorted(gaps),
            "not_started_skills": not_started,
            "in_learning_skills": learning,
            "gap_ratio": round(len(gaps) / len(all_skills), 4) if all_skills else 0.0,
        }

    def predict_next_skill_unlock(self, agent_id: str) -> list[dict[str, Any]]:
        """Predict which skills the agent is most likely to unlock next."""
        agent_recs = [r for r in self._records if r.agent_id == agent_id]
        learning_skills = [r for r in agent_recs if r.status == AcquisitionStatus.LEARNING]
        acquired_names = {
            r.skill_name
            for r in agent_recs
            if r.status in (AcquisitionStatus.ACQUIRED, AcquisitionStatus.MASTERED)
        }
        predictions: list[dict[str, Any]] = []
        for lr in learning_skills:
            prereq_met = not lr.prerequisite_skill or lr.prerequisite_skill in acquired_names
            unlock_probability = round(lr.proficiency_score * (1.2 if prereq_met else 0.5), 4)
            predictions.append(
                {
                    "skill_name": lr.skill_name,
                    "domain": lr.domain.value,
                    "current_proficiency": lr.proficiency_score,
                    "prerequisite_met": prereq_met,
                    "unlock_probability": min(1.0, unlock_probability),
                }
            )
        predictions.sort(key=lambda x: x["unlock_probability"], reverse=True)
        return predictions
