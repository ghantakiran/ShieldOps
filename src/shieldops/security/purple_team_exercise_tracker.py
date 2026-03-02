"""Purple Team Exercise Tracker — purple team exercise effectiveness tracking."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExerciseType(StrEnum):
    FULL_SIMULATION = "full_simulation"
    TABLETOP = "tabletop"
    ADVERSARY_EMULATION = "adversary_emulation"
    CONTROL_VALIDATION = "control_validation"
    DETECTION_TEST = "detection_test"


class ExerciseOutcome(StrEnum):
    ALL_DETECTED = "all_detected"
    MOSTLY_DETECTED = "mostly_detected"
    PARTIALLY_DETECTED = "partially_detected"
    MOSTLY_MISSED = "mostly_missed"
    ALL_MISSED = "all_missed"


class ControlEffectiveness(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    WEAK = "weak"
    INEFFECTIVE = "ineffective"


# --- Models ---


class ExerciseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exercise_name: str = ""
    exercise_type: ExerciseType = ExerciseType.FULL_SIMULATION
    exercise_outcome: ExerciseOutcome = ExerciseOutcome.ALL_DETECTED
    control_effectiveness: ControlEffectiveness = ControlEffectiveness.EXCELLENT
    effectiveness_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ExerciseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exercise_name: str = ""
    exercise_type: ExerciseType = ExerciseType.FULL_SIMULATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ExerciseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_effectiveness_count: int = 0
    avg_effectiveness_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_effectiveness: dict[str, int] = Field(default_factory=dict)
    top_low_effectiveness: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PurpleTeamExerciseTracker:
    """Track purple team exercise effectiveness and control validation."""

    def __init__(
        self,
        max_records: int = 200000,
        exercise_effectiveness_threshold: float = 65.0,
    ) -> None:
        self._max_records = max_records
        self._exercise_effectiveness_threshold = exercise_effectiveness_threshold
        self._records: list[ExerciseRecord] = []
        self._analyses: list[ExerciseAnalysis] = []
        logger.info(
            "purple_team_exercise_tracker.initialized",
            max_records=max_records,
            exercise_effectiveness_threshold=exercise_effectiveness_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_exercise(
        self,
        exercise_name: str,
        exercise_type: ExerciseType = ExerciseType.FULL_SIMULATION,
        exercise_outcome: ExerciseOutcome = ExerciseOutcome.ALL_DETECTED,
        control_effectiveness: ControlEffectiveness = ControlEffectiveness.EXCELLENT,
        effectiveness_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ExerciseRecord:
        record = ExerciseRecord(
            exercise_name=exercise_name,
            exercise_type=exercise_type,
            exercise_outcome=exercise_outcome,
            control_effectiveness=control_effectiveness,
            effectiveness_score=effectiveness_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "purple_team_exercise_tracker.exercise_recorded",
            record_id=record.id,
            exercise_name=exercise_name,
            exercise_type=exercise_type.value,
            exercise_outcome=exercise_outcome.value,
        )
        return record

    def get_exercise(self, record_id: str) -> ExerciseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_exercises(
        self,
        exercise_type: ExerciseType | None = None,
        exercise_outcome: ExerciseOutcome | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ExerciseRecord]:
        results = list(self._records)
        if exercise_type is not None:
            results = [r for r in results if r.exercise_type == exercise_type]
        if exercise_outcome is not None:
            results = [r for r in results if r.exercise_outcome == exercise_outcome]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        exercise_name: str,
        exercise_type: ExerciseType = ExerciseType.FULL_SIMULATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ExerciseAnalysis:
        analysis = ExerciseAnalysis(
            exercise_name=exercise_name,
            exercise_type=exercise_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "purple_team_exercise_tracker.analysis_added",
            exercise_name=exercise_name,
            exercise_type=exercise_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        """Group by exercise_type; return count and avg effectiveness_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.exercise_type.value
            type_data.setdefault(key, []).append(r.effectiveness_score)
        result: dict[str, Any] = {}
        for etype, scores in type_data.items():
            result[etype] = {
                "count": len(scores),
                "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_effectiveness_exercises(self) -> list[dict[str, Any]]:
        """Return records where effectiveness_score < exercise_effectiveness_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effectiveness_score < self._exercise_effectiveness_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "exercise_name": r.exercise_name,
                        "exercise_type": r.exercise_type.value,
                        "effectiveness_score": r.effectiveness_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["effectiveness_score"])

    def rank_by_effectiveness_score(self) -> list[dict[str, Any]]:
        """Group by service, avg effectiveness_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.effectiveness_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_effectiveness_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_effectiveness_score"])
        return results

    def detect_effectiveness_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ExerciseReport:
        by_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        by_effectiveness: dict[str, int] = {}
        for r in self._records:
            by_type[r.exercise_type.value] = by_type.get(r.exercise_type.value, 0) + 1
            by_outcome[r.exercise_outcome.value] = by_outcome.get(r.exercise_outcome.value, 0) + 1
            by_effectiveness[r.control_effectiveness.value] = (
                by_effectiveness.get(r.control_effectiveness.value, 0) + 1
            )
        low_effectiveness_count = sum(
            1
            for r in self._records
            if r.effectiveness_score < self._exercise_effectiveness_threshold
        )
        scores = [r.effectiveness_score for r in self._records]
        avg_effectiveness_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_effectiveness_exercises()
        top_low_effectiveness = [o["exercise_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_effectiveness_count > 0:
            recs.append(
                f"{low_effectiveness_count} exercise(s) below effectiveness threshold "
                f"({self._exercise_effectiveness_threshold})"
            )
        if self._records and avg_effectiveness_score < self._exercise_effectiveness_threshold:
            recs.append(
                f"Avg effectiveness score {avg_effectiveness_score} below threshold "
                f"({self._exercise_effectiveness_threshold})"
            )
        if not recs:
            recs.append("Purple team exercise effectiveness is healthy")
        return ExerciseReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_effectiveness_count=low_effectiveness_count,
            avg_effectiveness_score=avg_effectiveness_score,
            by_type=by_type,
            by_outcome=by_outcome,
            by_effectiveness=by_effectiveness,
            top_low_effectiveness=top_low_effectiveness,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("purple_team_exercise_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.exercise_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "exercise_effectiveness_threshold": self._exercise_effectiveness_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
