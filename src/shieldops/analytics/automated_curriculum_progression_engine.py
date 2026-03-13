"""Automated Curriculum Progression Engine —
progressive difficulty curriculum scheduling for SRE agent training."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CurriculumStage(StrEnum):
    FOUNDATION = "foundation"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    MASTERY = "mastery"


class ProgressionTrigger(StrEnum):
    SCORE_THRESHOLD = "score_threshold"
    ITERATION_COUNT = "iteration_count"
    PLATEAU_DETECTED = "plateau_detected"
    PROPOSER_SIGNAL = "proposer_signal"


class DifficultyAdjustment(StrEnum):
    INCREASE = "increase"
    MAINTAIN = "maintain"
    DECREASE = "decrease"
    RESET = "reset"


# --- Models ---


class CurriculumRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    curriculum_id: str = ""
    stage: CurriculumStage = CurriculumStage.FOUNDATION
    trigger: ProgressionTrigger = ProgressionTrigger.SCORE_THRESHOLD
    adjustment: DifficultyAdjustment = DifficultyAdjustment.MAINTAIN
    current_difficulty: float = 0.0
    solver_score: float = 0.0
    iteration: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CurriculumAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    curriculum_id: str = ""
    current_stage: CurriculumStage = CurriculumStage.FOUNDATION
    avg_difficulty: float = 0.0
    avg_solver_score: float = 0.0
    record_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CurriculumReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_difficulty: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_trigger: dict[str, int] = Field(default_factory=dict)
    by_adjustment: dict[str, int] = Field(default_factory=dict)
    top_curricula: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutomatedCurriculumProgressionEngine:
    """Progressive difficulty curriculum scheduling for SRE agent training."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CurriculumRecord] = []
        self._analyses: dict[str, CurriculumAnalysis] = {}
        logger.info(
            "automated_curriculum_progression_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        curriculum_id: str = "",
        stage: CurriculumStage = CurriculumStage.FOUNDATION,
        trigger: ProgressionTrigger = ProgressionTrigger.SCORE_THRESHOLD,
        adjustment: DifficultyAdjustment = DifficultyAdjustment.MAINTAIN,
        current_difficulty: float = 0.0,
        solver_score: float = 0.0,
        iteration: int = 0,
        description: str = "",
    ) -> CurriculumRecord:
        record = CurriculumRecord(
            curriculum_id=curriculum_id,
            stage=stage,
            trigger=trigger,
            adjustment=adjustment,
            current_difficulty=current_difficulty,
            solver_score=solver_score,
            iteration=iteration,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "automated_curriculum_progression.record_added",
            record_id=record.id,
            curriculum_id=curriculum_id,
        )
        return record

    def process(self, key: str) -> CurriculumAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        cur_recs = [r for r in self._records if r.curriculum_id == rec.curriculum_id]
        diffs = [r.current_difficulty for r in cur_recs]
        scores = [r.solver_score for r in cur_recs]
        avg_diff = round(sum(diffs) / len(diffs), 4) if diffs else 0.0
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        analysis = CurriculumAnalysis(
            curriculum_id=rec.curriculum_id,
            current_stage=rec.stage,
            avg_difficulty=avg_diff,
            avg_solver_score=avg_score,
            record_count=len(cur_recs),
            description=f"Curriculum {rec.curriculum_id} stage {rec.stage.value}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CurriculumReport:
        by_st: dict[str, int] = {}
        by_tr: dict[str, int] = {}
        by_adj: dict[str, int] = {}
        diffs: list[float] = []
        for r in self._records:
            k1 = r.stage.value
            by_st[k1] = by_st.get(k1, 0) + 1
            k2 = r.trigger.value
            by_tr[k2] = by_tr.get(k2, 0) + 1
            k3 = r.adjustment.value
            by_adj[k3] = by_adj.get(k3, 0) + 1
            diffs.append(r.current_difficulty)
        avg_diff = round(sum(diffs) / len(diffs), 4) if diffs else 0.0
        cur_scores: dict[str, float] = {}
        for r in self._records:
            if r.solver_score > cur_scores.get(r.curriculum_id, -1.0):
                cur_scores[r.curriculum_id] = r.solver_score
        top_curricula = sorted(
            cur_scores,
            key=lambda x: cur_scores[x],
            reverse=True,
        )[:10]
        recs_list: list[str] = []
        resets = by_adj.get("reset", 0)
        if resets > 0:
            recs_list.append(f"{resets} curriculum resets detected — review pacing")
        if not recs_list:
            recs_list.append("Curriculum progression is on track")
        return CurriculumReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_difficulty=avg_diff,
            by_stage=by_st,
            by_trigger=by_tr,
            by_adjustment=by_adj,
            top_curricula=top_curricula,
            recommendations=recs_list,
        )

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            k = r.stage.value
            stage_dist[k] = stage_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "stage_distribution": stage_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("automated_curriculum_progression_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def evaluate_progression_readiness(
        self,
        curriculum_id: str,
        score_threshold: float = 0.8,
    ) -> dict[str, Any]:
        """Evaluate whether a curriculum is ready to progress to next stage."""
        cur_recs = [r for r in self._records if r.curriculum_id == curriculum_id]
        if not cur_recs:
            return {"curriculum_id": curriculum_id, "ready": False, "reason": "no_data"}
        latest = max(cur_recs, key=lambda x: x.iteration)
        recent_recs = [r for r in cur_recs if r.iteration >= latest.iteration - 5]
        scores = [r.solver_score for r in recent_recs]
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        ready = avg_score >= score_threshold
        stages = list(CurriculumStage)
        current_idx = stages.index(latest.stage)
        next_stage = stages[min(current_idx + 1, len(stages) - 1)]
        return {
            "curriculum_id": curriculum_id,
            "current_stage": latest.stage.value,
            "avg_recent_score": avg_score,
            "score_threshold": score_threshold,
            "ready": ready,
            "next_stage": next_stage.value if ready else latest.stage.value,
            "trigger": ProgressionTrigger.SCORE_THRESHOLD.value,
        }

    def compute_optimal_difficulty_schedule(
        self,
        total_iterations: int = 100,
    ) -> list[dict[str, Any]]:
        """Compute optimal difficulty schedule across curriculum stages."""
        stages = list(CurriculumStage)
        stage_fractions = [0.25, 0.30, 0.30, 0.15]
        schedule: list[dict[str, Any]] = []
        cumulative = 0
        for i, stage in enumerate(stages):
            stage_iterations = int(total_iterations * stage_fractions[i])
            start_diff = 0.1 + i * 0.2
            end_diff = start_diff + 0.15
            for j in range(stage_iterations):
                iteration_num = cumulative + j
                frac = j / max(stage_iterations - 1, 1)
                difficulty = round(start_diff + frac * (end_diff - start_diff), 3)
                schedule.append(
                    {
                        "iteration": iteration_num,
                        "stage": stage.value,
                        "difficulty": difficulty,
                    }
                )
            cumulative += stage_iterations
        return schedule

    def track_curriculum_coverage(self) -> dict[str, Any]:
        """Track which stages have been covered and progression completeness."""
        cur_stages: dict[str, set[str]] = {}
        for r in self._records:
            cur_stages.setdefault(r.curriculum_id, set()).add(r.stage.value)
        all_stages = {s.value for s in CurriculumStage}
        coverage_report: list[dict[str, Any]] = []
        for cid, covered in cur_stages.items():
            missing = all_stages - covered
            coverage = round(len(covered) / len(all_stages), 4)
            coverage_report.append(
                {
                    "curriculum_id": cid,
                    "stages_covered": sorted(covered),
                    "stages_missing": sorted(missing),
                    "coverage_ratio": coverage,
                    "complete": len(missing) == 0,
                }
            )
        coverage_report.sort(key=lambda x: x["coverage_ratio"], reverse=True)
        return {
            "total_curricula": len(cur_stages),
            "coverage_details": coverage_report,
        }
