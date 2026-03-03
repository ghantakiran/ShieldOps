"""Chaos Experiment Scheduler — schedule and manage chaos experiments."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ExperimentType(StrEnum):
    LATENCY_INJECTION = "latency_injection"
    FAILURE_INJECTION = "failure_injection"
    RESOURCE_STRESS = "resource_stress"
    NETWORK_PARTITION = "network_partition"
    DNS_FAILURE = "dns_failure"


class ScheduleFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class ExperimentStatus(StrEnum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# --- Models ---


class ChaosExperiment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_type: ExperimentType = ExperimentType.LATENCY_INJECTION
    schedule_frequency: ScheduleFrequency = ScheduleFrequency.WEEKLY
    status: ExperimentStatus = ExperimentStatus.SCHEDULED
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ExperimentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_type: ExperimentType = ExperimentType.LATENCY_INJECTION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ExperimentScheduleReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_frequency: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChaosExperimentScheduler:
    """Schedule chaos experiments, track execution, and analyze resilience gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ChaosExperiment] = []
        self._analyses: list[ExperimentAnalysis] = []
        logger.info(
            "chaos_experiment_scheduler.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_experiment(
        self,
        service: str,
        experiment_type: ExperimentType = ExperimentType.LATENCY_INJECTION,
        schedule_frequency: ScheduleFrequency = ScheduleFrequency.WEEKLY,
        status: ExperimentStatus = ExperimentStatus.SCHEDULED,
        score: float = 0.0,
        team: str = "",
    ) -> ChaosExperiment:
        record = ChaosExperiment(
            experiment_type=experiment_type,
            schedule_frequency=schedule_frequency,
            status=status,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "chaos_experiment_scheduler.experiment_recorded",
            record_id=record.id,
            service=service,
            experiment_type=experiment_type.value,
            status=status.value,
        )
        return record

    def get_experiment(self, record_id: str) -> ChaosExperiment | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_experiments(
        self,
        experiment_type: ExperimentType | None = None,
        status: ExperimentStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ChaosExperiment]:
        results = list(self._records)
        if experiment_type is not None:
            results = [r for r in results if r.experiment_type == experiment_type]
        if status is not None:
            results = [r for r in results if r.status == status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        experiment_type: ExperimentType = ExperimentType.LATENCY_INJECTION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ExperimentAnalysis:
        analysis = ExperimentAnalysis(
            experiment_type=experiment_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "chaos_experiment_scheduler.analysis_added",
            experiment_type=experiment_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by experiment_type; return count and avg score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.experiment_type.value
            type_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for etype, scores in type_data.items():
            result[etype] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_coverage_gaps(self) -> list[dict[str, Any]]:
        """Return records where score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "experiment_type": r.experiment_type.value,
                        "score": r.score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_score_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ExperimentScheduleReport:
        by_type: dict[str, int] = {}
        by_frequency: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.experiment_type.value] = by_type.get(r.experiment_type.value, 0) + 1
            by_frequency[r.schedule_frequency.value] = (
                by_frequency.get(r.schedule_frequency.value, 0) + 1
            )
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_coverage_gaps()
        top_gaps = [o["service"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} experiment(s) below score threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Chaos experiment schedule is healthy")
        return ExperimentScheduleReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_type=by_type,
            by_frequency=by_frequency,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("chaos_experiment_scheduler.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.experiment_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
