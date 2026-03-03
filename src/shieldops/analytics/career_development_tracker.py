"""Career Development Tracker — track engineer growth and career progression."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CareerStage(StrEnum):
    JUNIOR = "junior"
    MID_LEVEL = "mid_level"
    SENIOR = "senior"
    STAFF = "staff"
    PRINCIPAL = "principal"


class DevelopmentArea(StrEnum):
    TECHNICAL = "technical"
    LEADERSHIP = "leadership"
    COMMUNICATION = "communication"
    DOMAIN = "domain"
    STRATEGIC = "strategic"


class ProgressStatus(StrEnum):
    ON_TRACK = "on_track"
    AHEAD = "ahead"
    BEHIND = "behind"
    STALLED = "stalled"
    UNDEFINED = "undefined"


# --- Models ---


class CareerRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str = ""
    team: str = ""
    career_stage: CareerStage = CareerStage.MID_LEVEL
    development_area: DevelopmentArea = DevelopmentArea.TECHNICAL
    progress_status: ProgressStatus = ProgressStatus.ON_TRACK
    progress_score: float = 0.0
    months_in_role: int = 0
    created_at: float = Field(default_factory=time.time)


class CareerAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str = ""
    development_area: DevelopmentArea = DevelopmentArea.TECHNICAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CareerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_progress_score: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_area: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CareerDevelopmentTracker:
    """Track engineer career progression and identify development gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[CareerRecord] = []
        self._analyses: list[CareerAnalysis] = []
        logger.info(
            "career_development_tracker.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_career(
        self,
        engineer: str,
        team: str = "",
        career_stage: CareerStage = CareerStage.MID_LEVEL,
        development_area: DevelopmentArea = DevelopmentArea.TECHNICAL,
        progress_status: ProgressStatus = ProgressStatus.ON_TRACK,
        progress_score: float = 0.0,
        months_in_role: int = 0,
    ) -> CareerRecord:
        record = CareerRecord(
            engineer=engineer,
            team=team,
            career_stage=career_stage,
            development_area=development_area,
            progress_status=progress_status,
            progress_score=progress_score,
            months_in_role=months_in_role,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "career_development_tracker.career_recorded",
            record_id=record.id,
            engineer=engineer,
            career_stage=career_stage.value,
            progress_status=progress_status.value,
        )
        return record

    def get_career(self, record_id: str) -> CareerRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_careers(
        self,
        career_stage: CareerStage | None = None,
        development_area: DevelopmentArea | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CareerRecord]:
        results = list(self._records)
        if career_stage is not None:
            results = [r for r in results if r.career_stage == career_stage]
        if development_area is not None:
            results = [r for r in results if r.development_area == development_area]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        engineer: str,
        development_area: DevelopmentArea = DevelopmentArea.TECHNICAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CareerAnalysis:
        analysis = CareerAnalysis(
            engineer=engineer,
            development_area=development_area,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "career_development_tracker.analysis_added",
            engineer=engineer,
            development_area=development_area.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by career_stage; return count and avg progress_score."""
        stage_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.career_stage.value
            stage_data.setdefault(key, []).append(r.progress_score)
        result: dict[str, Any] = {}
        for stage, scores in stage_data.items():
            result[stage] = {
                "count": len(scores),
                "avg_progress_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_development_gaps(self) -> list[dict[str, Any]]:
        """Return records where progress_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.progress_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "engineer": r.engineer,
                        "development_area": r.development_area.value,
                        "progress_score": r.progress_score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["progress_score"])

    def rank_by_progress(self) -> list[dict[str, Any]]:
        """Group by engineer, avg progress_score, sort ascending."""
        eng_scores: dict[str, list[float]] = {}
        for r in self._records:
            eng_scores.setdefault(r.engineer, []).append(r.progress_score)
        results: list[dict[str, Any]] = []
        for engineer, scores in eng_scores.items():
            results.append(
                {
                    "engineer": engineer,
                    "avg_progress_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_progress_score"])
        return results

    def detect_development_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
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

    def generate_report(self) -> CareerReport:
        by_stage: dict[str, int] = {}
        by_area: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_stage[r.career_stage.value] = by_stage.get(r.career_stage.value, 0) + 1
            by_area[r.development_area.value] = by_area.get(r.development_area.value, 0) + 1
            by_status[r.progress_status.value] = by_status.get(r.progress_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.progress_score < self._threshold)
        scores = [r.progress_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_development_gaps()
        top_gaps = [o["engineer"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} engineer(s) below progress threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg progress score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Career development is healthy")
        return CareerReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_progress_score=avg_score,
            by_stage=by_stage,
            by_area=by_area,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("career_development_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            key = r.career_stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "stage_distribution": stage_dist,
            "unique_engineers": len({r.engineer for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
