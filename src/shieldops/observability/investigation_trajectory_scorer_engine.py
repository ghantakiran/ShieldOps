"""Investigation Trajectory Scorer Engine —
score investigation path quality and efficiency,
identify trajectory inefficiencies, compare trajectories."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TrajectoryQuality(StrEnum):
    OPTIMAL = "optimal"
    GOOD = "good"
    SUBOPTIMAL = "suboptimal"
    WASTEFUL = "wasteful"


class ScoringDimension(StrEnum):
    EFFICIENCY = "efficiency"
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    TIMELINESS = "timeliness"


class DeviationType(StrEnum):
    UNNECESSARY_DETOUR = "unnecessary_detour"
    MISSED_SHORTCUT = "missed_shortcut"
    WRONG_BRANCH = "wrong_branch"
    PREMATURE_CONCLUSION = "premature_conclusion"


# --- Models ---


class InvestigationTrajectoryScorerRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    trajectory_quality: TrajectoryQuality = TrajectoryQuality.GOOD
    scoring_dimension: ScoringDimension = ScoringDimension.EFFICIENCY
    deviation_type: DeviationType = DeviationType.UNNECESSARY_DETOUR
    dimension_score: float = 0.0
    steps_taken: int = 0
    optimal_steps: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InvestigationTrajectoryScorerAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    trajectory_quality: TrajectoryQuality = TrajectoryQuality.GOOD
    scoring_dimension: ScoringDimension = ScoringDimension.EFFICIENCY
    deviation_type: DeviationType = DeviationType.UNNECESSARY_DETOUR
    overall_score: float = 0.0
    efficiency_ratio: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InvestigationTrajectoryScorerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_dimension_score: float = 0.0
    by_trajectory_quality: dict[str, int] = Field(default_factory=dict)
    by_scoring_dimension: dict[str, int] = Field(default_factory=dict)
    by_deviation_type: dict[str, int] = Field(default_factory=dict)
    top_investigations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class InvestigationTrajectoryScorerEngine:
    """Score investigation path quality and efficiency,
    identify trajectory inefficiencies, compare trajectories."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[InvestigationTrajectoryScorerRecord] = []
        self._analyses: dict[str, InvestigationTrajectoryScorerAnalysis] = {}
        logger.info("investigation_trajectory_scorer_engine.init", max_records=max_records)

    def add_record(
        self,
        investigation_id: str = "",
        trajectory_quality: TrajectoryQuality = TrajectoryQuality.GOOD,
        scoring_dimension: ScoringDimension = ScoringDimension.EFFICIENCY,
        deviation_type: DeviationType = DeviationType.UNNECESSARY_DETOUR,
        dimension_score: float = 0.0,
        steps_taken: int = 0,
        optimal_steps: int = 0,
        description: str = "",
    ) -> InvestigationTrajectoryScorerRecord:
        record = InvestigationTrajectoryScorerRecord(
            investigation_id=investigation_id,
            trajectory_quality=trajectory_quality,
            scoring_dimension=scoring_dimension,
            deviation_type=deviation_type,
            dimension_score=dimension_score,
            steps_taken=steps_taken,
            optimal_steps=optimal_steps,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "investigation_trajectory_scorer.record_added",
            record_id=record.id,
            investigation_id=investigation_id,
        )
        return record

    def process(self, key: str) -> InvestigationTrajectoryScorerAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        eff_ratio = (
            round(rec.optimal_steps / max(rec.steps_taken, 1), 4) if rec.optimal_steps else 0.0
        )
        quality_weights = {
            "optimal": 1.0,
            "good": 0.75,
            "suboptimal": 0.5,
            "wasteful": 0.25,
        }
        qw = quality_weights.get(rec.trajectory_quality.value, 0.5)
        overall = round(rec.dimension_score * qw, 4)
        analysis = InvestigationTrajectoryScorerAnalysis(
            investigation_id=rec.investigation_id,
            trajectory_quality=rec.trajectory_quality,
            scoring_dimension=rec.scoring_dimension,
            deviation_type=rec.deviation_type,
            overall_score=overall,
            efficiency_ratio=eff_ratio,
            description=(
                f"Investigation {rec.investigation_id} "
                f"quality={rec.trajectory_quality.value} "
                f"steps={rec.steps_taken}/{rec.optimal_steps}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> InvestigationTrajectoryScorerReport:
        by_tq: dict[str, int] = {}
        by_sd: dict[str, int] = {}
        by_dt: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.trajectory_quality.value
            by_tq[k] = by_tq.get(k, 0) + 1
            k2 = r.scoring_dimension.value
            by_sd[k2] = by_sd.get(k2, 0) + 1
            k3 = r.deviation_type.value
            by_dt[k3] = by_dt.get(k3, 0) + 1
            scores.append(r.dimension_score)
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        top: list[str] = list(
            {
                r.investigation_id
                for r in self._records
                if r.trajectory_quality == TrajectoryQuality.OPTIMAL
            }
        )[:10]
        recs: list[str] = []
        wasteful = by_tq.get("wasteful", 0)
        if wasteful:
            recs.append(f"{wasteful} wasteful investigation trajectories detected")
        wrong_branch = by_dt.get("wrong_branch", 0)
        if wrong_branch:
            recs.append(f"{wrong_branch} wrong-branch deviations — improve routing logic")
        if not recs:
            recs.append("Investigation trajectory quality is good")
        return InvestigationTrajectoryScorerReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_dimension_score=avg_score,
            by_trajectory_quality=by_tq,
            by_scoring_dimension=by_sd,
            by_deviation_type=by_dt,
            top_investigations=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.trajectory_quality.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "trajectory_quality_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("investigation_trajectory_scorer_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def score_investigation_trajectory(self) -> list[dict[str, Any]]:
        """Score each investigation's overall trajectory quality."""
        inv_map: dict[str, list[InvestigationTrajectoryScorerRecord]] = {}
        for r in self._records:
            inv_map.setdefault(r.investigation_id, []).append(r)
        quality_weights = {
            "optimal": 1.0,
            "good": 0.75,
            "suboptimal": 0.5,
            "wasteful": 0.25,
        }
        results: list[dict[str, Any]] = []
        for inv_id, inv_recs in inv_map.items():
            weighted_scores = [
                r.dimension_score * quality_weights.get(r.trajectory_quality.value, 0.5)
                for r in inv_recs
            ]
            avg_score = sum(weighted_scores) / len(weighted_scores)
            results.append(
                {
                    "investigation_id": inv_id,
                    "avg_trajectory_score": round(avg_score, 4),
                    "record_count": len(inv_recs),
                    "quality_counts": {
                        qv: sum(1 for r in inv_recs if r.trajectory_quality.value == qv)
                        for qv in quality_weights
                    },
                }
            )
        results.sort(key=lambda x: x["avg_trajectory_score"], reverse=True)
        return results

    def identify_trajectory_inefficiencies(self) -> list[dict[str, Any]]:
        """Identify investigations with wasteful or suboptimal trajectories."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.trajectory_quality in (TrajectoryQuality.WASTEFUL, TrajectoryQuality.SUBOPTIMAL)
                and r.investigation_id not in seen
            ):
                seen.add(r.investigation_id)
                eff = round(r.optimal_steps / max(r.steps_taken, 1), 4) if r.optimal_steps else 0.0
                results.append(
                    {
                        "investigation_id": r.investigation_id,
                        "trajectory_quality": r.trajectory_quality.value,
                        "deviation_type": r.deviation_type.value,
                        "steps_taken": r.steps_taken,
                        "optimal_steps": r.optimal_steps,
                        "efficiency_ratio": eff,
                    }
                )
        results.sort(key=lambda x: x["efficiency_ratio"])
        return results

    def compare_trajectories(self) -> list[dict[str, Any]]:
        """Compare trajectory scores across investigations."""
        inv_scores: dict[str, list[float]] = {}
        inv_steps: dict[str, int] = {}
        for r in self._records:
            inv_scores.setdefault(r.investigation_id, []).append(r.dimension_score)
            inv_steps[r.investigation_id] = inv_steps.get(r.investigation_id, 0) + r.steps_taken
        results: list[dict[str, Any]] = []
        for inv_id, score_list in inv_scores.items():
            avg_s = sum(score_list) / len(score_list)
            results.append(
                {
                    "investigation_id": inv_id,
                    "avg_score": round(avg_s, 4),
                    "total_steps": inv_steps[inv_id],
                    "sample_count": len(score_list),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_score"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
