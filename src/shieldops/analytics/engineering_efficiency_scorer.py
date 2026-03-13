"""Engineering Efficiency Scorer —
compute efficiency index, detect drains,
rank workflows by optimization potential."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EfficiencyDimension(StrEnum):
    BUILD_TIME = "build_time"
    REVIEW_CYCLE = "review_cycle"
    DEPLOY_FREQUENCY = "deploy_frequency"
    INCIDENT_RESPONSE = "incident_response"


class DrainType(StrEnum):
    TOOLING = "tooling"
    PROCESS = "process"
    COMMUNICATION = "communication"
    CONTEXT_SWITCHING = "context_switching"


class EfficiencyGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


# --- Models ---


class EfficiencyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    team_id: str = ""
    dimension: EfficiencyDimension = EfficiencyDimension.BUILD_TIME
    drain_type: DrainType = DrainType.TOOLING
    grade: EfficiencyGrade = EfficiencyGrade.GOOD
    efficiency_score: float = 0.0
    time_spent_hours: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EfficiencyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    avg_efficiency: float = 0.0
    grade: EfficiencyGrade = EfficiencyGrade.GOOD
    drain_count: int = 0
    total_time_hours: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EfficiencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_efficiency: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_drain: dict[str, int] = Field(default_factory=dict)
    by_grade: dict[str, int] = Field(default_factory=dict)
    top_drains: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EngineeringEfficiencyScorer:
    """Compute efficiency index, detect drains,
    rank workflows by optimization potential."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[EfficiencyRecord] = []
        self._analyses: dict[str, EfficiencyAnalysis] = {}
        logger.info(
            "engineering_efficiency_scorer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        workflow_id: str = "",
        team_id: str = "",
        dimension: EfficiencyDimension = (EfficiencyDimension.BUILD_TIME),
        drain_type: DrainType = DrainType.TOOLING,
        grade: EfficiencyGrade = EfficiencyGrade.GOOD,
        efficiency_score: float = 0.0,
        time_spent_hours: float = 0.0,
        description: str = "",
    ) -> EfficiencyRecord:
        record = EfficiencyRecord(
            workflow_id=workflow_id,
            team_id=team_id,
            dimension=dimension,
            drain_type=drain_type,
            grade=grade,
            efficiency_score=efficiency_score,
            time_spent_hours=time_spent_hours,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "engineering_efficiency.record_added",
            record_id=record.id,
            workflow_id=workflow_id,
        )
        return record

    def process(self, key: str) -> EfficiencyAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        wf_recs = [r for r in self._records if r.workflow_id == rec.workflow_id]
        scores = [r.efficiency_score for r in wf_recs]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        total_h = round(
            sum(r.time_spent_hours for r in wf_recs),
            2,
        )
        drains = sum(1 for r in wf_recs if r.grade in (EfficiencyGrade.FAIR, EfficiencyGrade.POOR))
        analysis = EfficiencyAnalysis(
            workflow_id=rec.workflow_id,
            avg_efficiency=avg,
            grade=rec.grade,
            drain_count=drains,
            total_time_hours=total_h,
            description=(f"Workflow {rec.workflow_id} eff={avg}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> EfficiencyReport:
        by_d: dict[str, int] = {}
        by_dr: dict[str, int] = {}
        by_g: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.dimension.value
            by_d[k] = by_d.get(k, 0) + 1
            k2 = r.drain_type.value
            by_dr[k2] = by_dr.get(k2, 0) + 1
            k3 = r.grade.value
            by_g[k3] = by_g.get(k3, 0) + 1
            scores.append(r.efficiency_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        drain_totals: dict[str, float] = {}
        for r in self._records:
            dt = r.drain_type.value
            drain_totals[dt] = drain_totals.get(dt, 0.0) + r.time_spent_hours
        top = sorted(
            drain_totals,
            key=lambda x: drain_totals[x],
            reverse=True,
        )[:10]
        recs: list[str] = []
        poor = by_g.get("poor", 0)
        if poor > 0:
            recs.append(f"{poor} poor efficiency scores")
        if not recs:
            recs.append("Efficiency levels acceptable")
        return EfficiencyReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_efficiency=avg,
            by_dimension=by_d,
            by_drain=by_dr,
            by_grade=by_g,
            top_drains=top,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        d_dist: dict[str, int] = {}
        for r in self._records:
            k = r.dimension.value
            d_dist[k] = d_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "dimension_distribution": d_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("engineering_efficiency_scorer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_efficiency_index(
        self,
    ) -> list[dict[str, Any]]:
        """Compute efficiency index per workflow."""
        wf_scores: dict[str, list[float]] = {}
        wf_hours: dict[str, float] = {}
        for r in self._records:
            wf_scores.setdefault(r.workflow_id, []).append(r.efficiency_score)
            wf_hours[r.workflow_id] = wf_hours.get(r.workflow_id, 0.0) + r.time_spent_hours
        results: list[dict[str, Any]] = []
        for wid, scores in wf_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "workflow_id": wid,
                    "efficiency_index": avg,
                    "total_hours": round(wf_hours.get(wid, 0.0), 2),
                    "samples": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["efficiency_index"],
            reverse=True,
        )
        return results

    def detect_efficiency_drains(
        self,
    ) -> list[dict[str, Any]]:
        """Detect efficiency drains by type."""
        drain_hours: dict[str, float] = {}
        drain_counts: dict[str, int] = {}
        for r in self._records:
            if r.grade in (
                EfficiencyGrade.FAIR,
                EfficiencyGrade.POOR,
            ):
                dt = r.drain_type.value
                drain_hours[dt] = drain_hours.get(dt, 0.0) + r.time_spent_hours
                drain_counts[dt] = drain_counts.get(dt, 0) + 1
        results: list[dict[str, Any]] = []
        for dt, hours in drain_hours.items():
            results.append(
                {
                    "drain_type": dt,
                    "total_hours": round(hours, 2),
                    "occurrences": drain_counts.get(dt, 0),
                }
            )
        results.sort(
            key=lambda x: x["total_hours"],
            reverse=True,
        )
        return results

    def rank_workflows_by_optimization_potential(
        self,
    ) -> list[dict[str, Any]]:
        """Rank workflows by optimization potential."""
        wf_scores: dict[str, list[float]] = {}
        wf_hours: dict[str, float] = {}
        for r in self._records:
            wf_scores.setdefault(r.workflow_id, []).append(r.efficiency_score)
            wf_hours[r.workflow_id] = wf_hours.get(r.workflow_id, 0.0) + r.time_spent_hours
        results: list[dict[str, Any]] = []
        for wid, scores in wf_scores.items():
            avg = sum(scores) / len(scores)
            potential = round(
                (100.0 - avg) * wf_hours.get(wid, 0.0) / 100.0,
                2,
            )
            results.append(
                {
                    "workflow_id": wid,
                    "optimization_potential": potential,
                    "current_efficiency": round(avg, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["optimization_potential"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
