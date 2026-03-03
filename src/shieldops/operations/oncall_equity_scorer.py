"""Oncall Equity Scorer — measure and improve on-call fairness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EquityMetric(StrEnum):
    PAGE_DISTRIBUTION = "page_distribution"
    HOURS_WORKED = "hours_worked"
    WEEKEND_RATIO = "weekend_ratio"
    NIGHT_RATIO = "night_ratio"
    INCIDENT_SEVERITY = "incident_severity"


class FairnessLevel(StrEnum):
    EQUITABLE = "equitable"
    SLIGHT_IMBALANCE = "slight_imbalance"
    MODERATE_IMBALANCE = "moderate_imbalance"
    SEVERE_IMBALANCE = "severe_imbalance"
    CRITICAL = "critical"


class CompensationType(StrEnum):
    TIME_OFF = "time_off"
    BONUS = "bonus"
    ROTATION = "rotation"
    REDUCED_LOAD = "reduced_load"
    NONE = "none"


# --- Models ---


class EquityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str = ""
    team: str = ""
    equity_metric: EquityMetric = EquityMetric.PAGE_DISTRIBUTION
    fairness_level: FairnessLevel = FairnessLevel.EQUITABLE
    compensation_type: CompensationType = CompensationType.NONE
    equity_score: float = 0.0
    page_count: int = 0
    created_at: float = Field(default_factory=time.time)


class EquityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engineer: str = ""
    equity_metric: EquityMetric = EquityMetric.PAGE_DISTRIBUTION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EquityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_equity_score: float = 0.0
    by_metric: dict[str, int] = Field(default_factory=dict)
    by_fairness: dict[str, int] = Field(default_factory=dict)
    by_compensation: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class OncallEquityScorer:
    """Measure on-call page distribution fairness and recommend compensation."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[EquityRecord] = []
        self._analyses: list[EquityAnalysis] = []
        logger.info(
            "oncall_equity_scorer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_equity(
        self,
        engineer: str,
        team: str = "",
        equity_metric: EquityMetric = EquityMetric.PAGE_DISTRIBUTION,
        fairness_level: FairnessLevel = FairnessLevel.EQUITABLE,
        compensation_type: CompensationType = CompensationType.NONE,
        equity_score: float = 0.0,
        page_count: int = 0,
    ) -> EquityRecord:
        record = EquityRecord(
            engineer=engineer,
            team=team,
            equity_metric=equity_metric,
            fairness_level=fairness_level,
            compensation_type=compensation_type,
            equity_score=equity_score,
            page_count=page_count,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "oncall_equity_scorer.equity_recorded",
            record_id=record.id,
            engineer=engineer,
            equity_metric=equity_metric.value,
            fairness_level=fairness_level.value,
        )
        return record

    def get_equity(self, record_id: str) -> EquityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_equities(
        self,
        equity_metric: EquityMetric | None = None,
        fairness_level: FairnessLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EquityRecord]:
        results = list(self._records)
        if equity_metric is not None:
            results = [r for r in results if r.equity_metric == equity_metric]
        if fairness_level is not None:
            results = [r for r in results if r.fairness_level == fairness_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        engineer: str,
        equity_metric: EquityMetric = EquityMetric.PAGE_DISTRIBUTION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> EquityAnalysis:
        analysis = EquityAnalysis(
            engineer=engineer,
            equity_metric=equity_metric,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "oncall_equity_scorer.analysis_added",
            engineer=engineer,
            equity_metric=equity_metric.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by equity_metric; return count and avg equity_score."""
        metric_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.equity_metric.value
            metric_data.setdefault(key, []).append(r.equity_score)
        result: dict[str, Any] = {}
        for metric, scores in metric_data.items():
            result[metric] = {
                "count": len(scores),
                "avg_equity_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_equity_gaps(self) -> list[dict[str, Any]]:
        """Return records where equity_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.equity_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "engineer": r.engineer,
                        "equity_metric": r.equity_metric.value,
                        "equity_score": r.equity_score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["equity_score"])

    def rank_by_equity(self) -> list[dict[str, Any]]:
        """Group by engineer, avg equity_score, sort ascending."""
        eng_scores: dict[str, list[float]] = {}
        for r in self._records:
            eng_scores.setdefault(r.engineer, []).append(r.equity_score)
        results: list[dict[str, Any]] = []
        for engineer, scores in eng_scores.items():
            results.append(
                {
                    "engineer": engineer,
                    "avg_equity_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_equity_score"])
        return results

    def detect_equity_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> EquityReport:
        by_metric: dict[str, int] = {}
        by_fairness: dict[str, int] = {}
        by_compensation: dict[str, int] = {}
        for r in self._records:
            by_metric[r.equity_metric.value] = by_metric.get(r.equity_metric.value, 0) + 1
            by_fairness[r.fairness_level.value] = by_fairness.get(r.fairness_level.value, 0) + 1
            by_compensation[r.compensation_type.value] = (
                by_compensation.get(r.compensation_type.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.equity_score < self._threshold)
        scores = [r.equity_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_equity_gaps()
        top_gaps = [o["engineer"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} engineer(s) below equity threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg equity score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Oncall equity is healthy")
        return EquityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_equity_score=avg_score,
            by_metric=by_metric,
            by_fairness=by_fairness,
            by_compensation=by_compensation,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("oncall_equity_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        metric_dist: dict[str, int] = {}
        for r in self._records:
            key = r.equity_metric.value
            metric_dist[key] = metric_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "metric_distribution": metric_dist,
            "unique_engineers": len({r.engineer for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
