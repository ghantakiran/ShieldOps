"""Team Capacity Predictor — forecast team capacity across dimensions."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CapacityDimension(StrEnum):
    ENGINEERING = "engineering"
    OPERATIONS = "operations"
    SECURITY = "security"
    MANAGEMENT = "management"
    SUPPORT = "support"


class UtilizationLevel(StrEnum):
    OVER = "over"
    HIGH = "high"
    OPTIMAL = "optimal"
    LOW = "low"
    IDLE = "idle"


class PredictionHorizon(StrEnum):
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    HALF_YEAR = "half_year"
    YEAR = "year"


# --- Models ---


class CapacityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team: str = ""
    dimension: CapacityDimension = CapacityDimension.ENGINEERING
    utilization_level: UtilizationLevel = UtilizationLevel.OPTIMAL
    horizon: PredictionHorizon = PredictionHorizon.MONTH
    utilization_score: float = 0.0
    headcount: int = 0
    created_at: float = Field(default_factory=time.time)


class CapacityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team: str = ""
    dimension: CapacityDimension = CapacityDimension.ENGINEERING
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_utilization_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_utilization: dict[str, int] = Field(default_factory=dict)
    by_horizon: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamCapacityPredictor:
    """Forecast team capacity across engineering, ops, security dimensions."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[CapacityRecord] = []
        self._analyses: list[CapacityAnalysis] = []
        logger.info(
            "team_capacity_predictor.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_capacity(
        self,
        team: str,
        dimension: CapacityDimension = CapacityDimension.ENGINEERING,
        utilization_level: UtilizationLevel = UtilizationLevel.OPTIMAL,
        horizon: PredictionHorizon = PredictionHorizon.MONTH,
        utilization_score: float = 0.0,
        headcount: int = 0,
    ) -> CapacityRecord:
        record = CapacityRecord(
            team=team,
            dimension=dimension,
            utilization_level=utilization_level,
            horizon=horizon,
            utilization_score=utilization_score,
            headcount=headcount,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "team_capacity_predictor.capacity_recorded",
            record_id=record.id,
            team=team,
            dimension=dimension.value,
            utilization_level=utilization_level.value,
        )
        return record

    def get_capacity(self, record_id: str) -> CapacityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_capacities(
        self,
        dimension: CapacityDimension | None = None,
        utilization_level: UtilizationLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CapacityRecord]:
        results = list(self._records)
        if dimension is not None:
            results = [r for r in results if r.dimension == dimension]
        if utilization_level is not None:
            results = [r for r in results if r.utilization_level == utilization_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        team: str,
        dimension: CapacityDimension = CapacityDimension.ENGINEERING,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CapacityAnalysis:
        analysis = CapacityAnalysis(
            team=team,
            dimension=dimension,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "team_capacity_predictor.analysis_added",
            team=team,
            dimension=dimension.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by dimension; return count and avg utilization_score."""
        dim_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.dimension.value
            dim_data.setdefault(key, []).append(r.utilization_score)
        result: dict[str, Any] = {}
        for dim, scores in dim_data.items():
            result[dim] = {
                "count": len(scores),
                "avg_utilization_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_capacity_gaps(self) -> list[dict[str, Any]]:
        """Return records where utilization_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.utilization_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "team": r.team,
                        "dimension": r.dimension.value,
                        "utilization_score": r.utilization_score,
                        "headcount": r.headcount,
                    }
                )
        return sorted(results, key=lambda x: x["utilization_score"])

    def rank_by_utilization(self) -> list[dict[str, Any]]:
        """Group by team, avg utilization_score, sort ascending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.utilization_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_utilization_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_utilization_score"])
        return results

    def detect_capacity_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> CapacityReport:
        by_dimension: dict[str, int] = {}
        by_utilization: dict[str, int] = {}
        by_horizon: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.dimension.value] = by_dimension.get(r.dimension.value, 0) + 1
            by_utilization[r.utilization_level.value] = (
                by_utilization.get(r.utilization_level.value, 0) + 1
            )
            by_horizon[r.horizon.value] = by_horizon.get(r.horizon.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.utilization_score < self._threshold)
        scores = [r.utilization_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_capacity_gaps()
        top_gaps = [o["team"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} team(s) below utilization threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg utilization score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Team capacity is healthy")
        return CapacityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_utilization_score=avg_score,
            by_dimension=by_dimension,
            by_utilization=by_utilization,
            by_horizon=by_horizon,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("team_capacity_predictor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dim_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dimension.value
            dim_dist[key] = dim_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "dimension_distribution": dim_dist,
            "unique_teams": len({r.team for r in self._records}),
        }
