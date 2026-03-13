"""Agent Curriculum Learning Engine —
design progressive learning curricula, evaluate progression
readiness, and optimize difficulty scheduling for agents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DifficultyLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class CurriculumPhase(StrEnum):
    WARMUP = "warmup"
    TRAINING = "training"
    EVALUATION = "evaluation"
    MASTERY = "mastery"


class LearningProgress(StrEnum):
    BEHIND = "behind"
    ON_TRACK = "on_track"
    AHEAD = "ahead"
    COMPLETED = "completed"


# --- Models ---


class CurriculumLearningRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    difficulty: DifficultyLevel = DifficultyLevel.BEGINNER
    phase: CurriculumPhase = CurriculumPhase.WARMUP
    progress: LearningProgress = LearningProgress.ON_TRACK
    task_score: float = 0.0
    completion_rate: float = 0.0
    episodes_completed: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CurriculumLearningAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    avg_task_score: float = 0.0
    current_difficulty: DifficultyLevel = DifficultyLevel.BEGINNER
    current_phase: CurriculumPhase = CurriculumPhase.WARMUP
    avg_completion_rate: float = 0.0
    record_count: int = 0
    readiness_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CurriculumLearningReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_task_score: float = 0.0
    by_difficulty: dict[str, int] = Field(default_factory=dict)
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_progress: dict[str, int] = Field(default_factory=dict)
    top_agents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentCurriculumLearningEngine:
    """Design progressive task difficulty for agent training,
    evaluate readiness, and optimize difficulty scheduling."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CurriculumLearningRecord] = []
        self._analyses: dict[str, CurriculumLearningAnalysis] = {}
        logger.info(
            "agent_curriculum_learning.init",
            max_records=max_records,
        )

    def add_record(
        self,
        agent_id: str = "",
        difficulty: DifficultyLevel = DifficultyLevel.BEGINNER,
        phase: CurriculumPhase = CurriculumPhase.WARMUP,
        progress: LearningProgress = LearningProgress.ON_TRACK,
        task_score: float = 0.0,
        completion_rate: float = 0.0,
        episodes_completed: int = 0,
        description: str = "",
    ) -> CurriculumLearningRecord:
        record = CurriculumLearningRecord(
            agent_id=agent_id,
            difficulty=difficulty,
            phase=phase,
            progress=progress,
            task_score=task_score,
            completion_rate=completion_rate,
            episodes_completed=episodes_completed,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "curriculum_learning.record_added",
            record_id=record.id,
            agent_id=agent_id,
        )
        return record

    def process(self, key: str) -> CurriculumLearningAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        agent_recs = [r for r in self._records if r.agent_id == rec.agent_id]
        scores = [r.task_score for r in agent_recs]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        comp_rates = [r.completion_rate for r in agent_recs]
        avg_comp = round(sum(comp_rates) / len(comp_rates), 2) if comp_rates else 0.0
        readiness = round(avg_score * avg_comp, 2)
        analysis = CurriculumLearningAnalysis(
            agent_id=rec.agent_id,
            avg_task_score=avg_score,
            current_difficulty=rec.difficulty,
            current_phase=rec.phase,
            avg_completion_rate=avg_comp,
            record_count=len(agent_recs),
            readiness_score=readiness,
            description=f"Agent {rec.agent_id} readiness {readiness}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CurriculumLearningReport:
        by_d: dict[str, int] = {}
        by_p: dict[str, int] = {}
        by_pr: dict[str, int] = {}
        vals: list[float] = []
        for r in self._records:
            by_d[r.difficulty.value] = by_d.get(r.difficulty.value, 0) + 1
            by_p[r.phase.value] = by_p.get(r.phase.value, 0) + 1
            by_pr[r.progress.value] = by_pr.get(r.progress.value, 0) + 1
            vals.append(r.task_score)
        avg = round(sum(vals) / len(vals), 2) if vals else 0.0
        agent_totals: dict[str, float] = {}
        for r in self._records:
            agent_totals[r.agent_id] = agent_totals.get(r.agent_id, 0.0) + r.task_score
        ranked = sorted(
            agent_totals,
            key=lambda x: agent_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        behind = by_pr.get("behind", 0)
        if behind > 0:
            recs.append(f"{behind} agents behind schedule — reduce difficulty")
        if not recs:
            recs.append("Curriculum progression is on track")
        return CurriculumLearningReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_task_score=avg,
            by_difficulty=by_d,
            by_phase=by_p,
            by_progress=by_pr,
            top_agents=ranked,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            dist[r.difficulty.value] = dist.get(r.difficulty.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "difficulty_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("agent_curriculum_learning.cleared")
        return {"status": "cleared"}

    # -- domain methods --

    def design_learning_curriculum(self) -> list[dict[str, Any]]:
        """Design a progressive learning curriculum per agent."""
        agent_data: dict[str, list[CurriculumLearningRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        difficulty_order = [
            DifficultyLevel.BEGINNER,
            DifficultyLevel.INTERMEDIATE,
            DifficultyLevel.ADVANCED,
            DifficultyLevel.EXPERT,
        ]
        for aid, recs in agent_data.items():
            scores = [r.task_score for r in recs]
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
            current_diff = recs[-1].difficulty if recs else DifficultyLevel.BEGINNER
            idx = difficulty_order.index(current_diff)
            next_diff = difficulty_order[min(idx + 1, len(difficulty_order) - 1)]
            should_advance = avg_score >= 0.8
            results.append(
                {
                    "agent_id": aid,
                    "avg_score": avg_score,
                    "current_difficulty": current_diff.value,
                    "recommended_next": next_diff.value if should_advance else current_diff.value,
                    "should_advance": should_advance,
                    "episode_count": sum(r.episodes_completed for r in recs),
                }
            )
        results.sort(key=lambda x: x["avg_score"], reverse=True)
        return results

    def evaluate_progression_readiness(self) -> list[dict[str, Any]]:
        """Evaluate whether each agent is ready to advance difficulty."""
        agent_data: dict[str, list[CurriculumLearningRecord]] = {}
        for r in self._records:
            agent_data.setdefault(r.agent_id, []).append(r)
        results: list[dict[str, Any]] = []
        for aid, recs in agent_data.items():
            scores = [r.task_score for r in recs]
            comp_rates = [r.completion_rate for r in recs]
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
            avg_comp = round(sum(comp_rates) / len(comp_rates), 2) if comp_rates else 0.0
            readiness = round(avg_score * 0.6 + avg_comp * 0.4, 2)
            ready = readiness >= 0.75
            results.append(
                {
                    "agent_id": aid,
                    "avg_task_score": avg_score,
                    "avg_completion_rate": avg_comp,
                    "readiness_score": readiness,
                    "ready_to_advance": ready,
                    "record_count": len(recs),
                }
            )
        results.sort(key=lambda x: x["readiness_score"], reverse=True)
        return results

    def optimize_difficulty_scheduling(self) -> list[dict[str, Any]]:
        """Optimize when to schedule difficulty increases."""
        difficulty_data: dict[str, list[float]] = {}
        for r in self._records:
            difficulty_data.setdefault(r.difficulty.value, []).append(r.task_score)
        results: list[dict[str, Any]] = []
        thresholds = {
            "beginner": 0.7,
            "intermediate": 0.75,
            "advanced": 0.8,
            "expert": 0.9,
        }
        for diff, scores in difficulty_data.items():
            avg_s = round(sum(scores) / len(scores), 2) if scores else 0.0
            threshold = thresholds.get(diff, 0.8)
            optimal = avg_s >= threshold
            results.append(
                {
                    "difficulty": diff,
                    "avg_score": avg_s,
                    "advance_threshold": threshold,
                    "schedule_optimal": optimal,
                    "gap_to_threshold": round(max(0.0, threshold - avg_s), 2),
                    "sample_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["gap_to_threshold"])
        return results
