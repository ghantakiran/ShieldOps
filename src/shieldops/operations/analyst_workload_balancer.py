"""Analyst Workload Balancer — SOC analyst workload tracking and shift optimization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ShiftType(StrEnum):
    DAY = "day"
    NIGHT = "night"
    SWING = "swing"
    WEEKEND = "weekend"
    ON_CALL = "on_call"


class WorkloadLevel(StrEnum):
    OVERLOADED = "overloaded"
    HIGH = "high"
    BALANCED = "balanced"
    LOW = "low"
    IDLE = "idle"


class SkillLevel(StrEnum):
    EXPERT = "expert"
    SENIOR = "senior"
    MID = "mid"
    JUNIOR = "junior"
    TRAINEE = "trainee"


# --- Models ---


class WorkloadRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    analyst_name: str = ""
    shift_type: ShiftType = ShiftType.DAY
    workload_level: WorkloadLevel = WorkloadLevel.OVERLOADED
    skill_level: SkillLevel = SkillLevel.EXPERT
    utilization_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkloadAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    analyst_name: str = ""
    shift_type: ShiftType = ShiftType.DAY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkloadReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    overloaded_count: int = 0
    avg_utilization_score: float = 0.0
    by_shift: dict[str, int] = Field(default_factory=dict)
    by_workload: dict[str, int] = Field(default_factory=dict)
    by_skill: dict[str, int] = Field(default_factory=dict)
    top_overloaded: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AnalystWorkloadBalancer:
    """SOC analyst workload tracking and shift optimization."""

    def __init__(
        self,
        max_records: int = 200000,
        utilization_threshold: float = 85.0,
    ) -> None:
        self._max_records = max_records
        self._utilization_threshold = utilization_threshold
        self._records: list[WorkloadRecord] = []
        self._analyses: list[WorkloadAnalysis] = []
        logger.info(
            "analyst_workload_balancer.initialized",
            max_records=max_records,
            utilization_threshold=utilization_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_workload(
        self,
        analyst_name: str,
        shift_type: ShiftType = ShiftType.DAY,
        workload_level: WorkloadLevel = WorkloadLevel.OVERLOADED,
        skill_level: SkillLevel = SkillLevel.EXPERT,
        utilization_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> WorkloadRecord:
        record = WorkloadRecord(
            analyst_name=analyst_name,
            shift_type=shift_type,
            workload_level=workload_level,
            skill_level=skill_level,
            utilization_score=utilization_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "analyst_workload_balancer.workload_recorded",
            record_id=record.id,
            analyst_name=analyst_name,
            shift_type=shift_type.value,
            workload_level=workload_level.value,
        )
        return record

    def get_workload(self, record_id: str) -> WorkloadRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_workloads(
        self,
        shift_type: ShiftType | None = None,
        workload_level: WorkloadLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WorkloadRecord]:
        results = list(self._records)
        if shift_type is not None:
            results = [r for r in results if r.shift_type == shift_type]
        if workload_level is not None:
            results = [r for r in results if r.workload_level == workload_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        analyst_name: str,
        shift_type: ShiftType = ShiftType.DAY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> WorkloadAnalysis:
        analysis = WorkloadAnalysis(
            analyst_name=analyst_name,
            shift_type=shift_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "analyst_workload_balancer.analysis_added",
            analyst_name=analyst_name,
            shift_type=shift_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_workload_distribution(self) -> dict[str, Any]:
        """Group by shift_type; return count and avg utilization_score."""
        src_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.shift_type.value
            src_data.setdefault(key, []).append(r.utilization_score)
        result: dict[str, Any] = {}
        for src, scores in src_data.items():
            result[src] = {
                "count": len(scores),
                "avg_utilization_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_overloaded_analysts(self) -> list[dict[str, Any]]:
        """Return records where utilization_score > utilization_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.utilization_score > self._utilization_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "analyst_name": r.analyst_name,
                        "shift_type": r.shift_type.value,
                        "utilization_score": r.utilization_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["utilization_score"], reverse=True)

    def rank_by_utilization(self) -> list[dict[str, Any]]:
        """Group by service, avg utilization_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.utilization_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_utilization_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_utilization_score"], reverse=True)
        return results

    def detect_workload_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> WorkloadReport:
        by_shift: dict[str, int] = {}
        by_workload: dict[str, int] = {}
        by_skill: dict[str, int] = {}
        for r in self._records:
            by_shift[r.shift_type.value] = by_shift.get(r.shift_type.value, 0) + 1
            by_workload[r.workload_level.value] = by_workload.get(r.workload_level.value, 0) + 1
            by_skill[r.skill_level.value] = by_skill.get(r.skill_level.value, 0) + 1
        overloaded_count = sum(
            1 for r in self._records if r.utilization_score > self._utilization_threshold
        )
        scores = [r.utilization_score for r in self._records]
        avg_utilization_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        overloaded_list = self.identify_overloaded_analysts()
        top_overloaded = [o["analyst_name"] for o in overloaded_list[:5]]
        recs: list[str] = []
        if self._records and overloaded_count > 0:
            recs.append(
                f"{overloaded_count} analyst(s) above utilization threshold "
                f"({self._utilization_threshold})"
            )
        if self._records and avg_utilization_score > self._utilization_threshold:
            recs.append(
                f"Avg utilization score {avg_utilization_score} above threshold "
                f"({self._utilization_threshold})"
            )
        if not recs:
            recs.append("Analyst workload balance is healthy")
        return WorkloadReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            overloaded_count=overloaded_count,
            avg_utilization_score=avg_utilization_score,
            by_shift=by_shift,
            by_workload=by_workload,
            by_skill=by_skill,
            top_overloaded=top_overloaded,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("analyst_workload_balancer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        shift_dist: dict[str, int] = {}
        for r in self._records:
            key = r.shift_type.value
            shift_dist[key] = shift_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "utilization_threshold": self._utilization_threshold,
            "shift_distribution": shift_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
