"""Workflow Efficiency Analyzer — analyze workflow efficiency, identify bottlenecks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WorkflowType(StrEnum):
    INCIDENT_RESPONSE = "incident_response"
    DEPLOYMENT = "deployment"
    CHANGE_MANAGEMENT = "change_management"
    SECURITY_REVIEW = "security_review"
    MAINTENANCE = "maintenance"


class EfficiencyLevel(StrEnum):
    OPTIMAL = "optimal"
    EFFICIENT = "efficient"
    ACCEPTABLE = "acceptable"
    INEFFICIENT = "inefficient"
    BROKEN = "broken"


class BottleneckType(StrEnum):
    APPROVAL_DELAY = "approval_delay"
    MANUAL_STEP = "manual_step"
    HANDOFF_GAP = "handoff_gap"
    TOOL_LIMITATION = "tool_limitation"
    PROCESS_GAP = "process_gap"


# --- Models ---


class WorkflowRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str = ""
    workflow_type: WorkflowType = WorkflowType.INCIDENT_RESPONSE
    efficiency_level: EfficiencyLevel = EfficiencyLevel.ACCEPTABLE
    bottleneck_type: BottleneckType = BottleneckType.MANUAL_STEP
    efficiency_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkflowStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_pattern: str = ""
    workflow_type: WorkflowType = WorkflowType.INCIDENT_RESPONSE
    duration_minutes: float = 0.0
    automation_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkflowEfficiencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_steps: int = 0
    efficient_workflows: int = 0
    avg_efficiency_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_bottleneck: dict[str, int] = Field(default_factory=dict)
    inefficient: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class WorkflowEfficiencyAnalyzer:
    """Analyze workflow efficiency, identify bottlenecks, track improvement trends."""

    def __init__(
        self,
        max_records: int = 200000,
        min_efficiency_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_efficiency_score = min_efficiency_score
        self._records: list[WorkflowRecord] = []
        self._steps: list[WorkflowStep] = []
        logger.info(
            "workflow_analyzer.initialized",
            max_records=max_records,
            min_efficiency_score=min_efficiency_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_workflow(
        self,
        workflow_id: str,
        workflow_type: WorkflowType = WorkflowType.INCIDENT_RESPONSE,
        efficiency_level: EfficiencyLevel = EfficiencyLevel.ACCEPTABLE,
        bottleneck_type: BottleneckType = BottleneckType.MANUAL_STEP,
        efficiency_score: float = 0.0,
        team: str = "",
    ) -> WorkflowRecord:
        record = WorkflowRecord(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            efficiency_level=efficiency_level,
            bottleneck_type=bottleneck_type,
            efficiency_score=efficiency_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "workflow_analyzer.workflow_recorded",
            record_id=record.id,
            workflow_id=workflow_id,
            workflow_type=workflow_type.value,
            efficiency_level=efficiency_level.value,
        )
        return record

    def get_workflow(self, record_id: str) -> WorkflowRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_workflows(
        self,
        workflow_type: WorkflowType | None = None,
        efficiency_level: EfficiencyLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowRecord]:
        results = list(self._records)
        if workflow_type is not None:
            results = [r for r in results if r.workflow_type == workflow_type]
        if efficiency_level is not None:
            results = [r for r in results if r.efficiency_level == efficiency_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_step(
        self,
        step_pattern: str,
        workflow_type: WorkflowType = WorkflowType.INCIDENT_RESPONSE,
        duration_minutes: float = 0.0,
        automation_pct: float = 0.0,
        description: str = "",
    ) -> WorkflowStep:
        step = WorkflowStep(
            step_pattern=step_pattern,
            workflow_type=workflow_type,
            duration_minutes=duration_minutes,
            automation_pct=automation_pct,
            description=description,
        )
        self._steps.append(step)
        if len(self._steps) > self._max_records:
            self._steps = self._steps[-self._max_records :]
        logger.info(
            "workflow_analyzer.step_added",
            step_pattern=step_pattern,
            workflow_type=workflow_type.value,
            duration_minutes=duration_minutes,
        )
        return step

    # -- domain operations --------------------------------------------------

    def analyze_workflow_efficiency(self) -> dict[str, Any]:
        """Group by workflow_type; return count and avg efficiency_score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.workflow_type.value
            type_data.setdefault(key, []).append(r.efficiency_score)
        result: dict[str, Any] = {}
        for wtype, scores in type_data.items():
            result[wtype] = {
                "count": len(scores),
                "avg_efficiency_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_inefficient_workflows(self) -> list[dict[str, Any]]:
        """Return records where efficiency_score < min_efficiency_score."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.efficiency_score < self._min_efficiency_score:
                results.append(
                    {
                        "record_id": r.id,
                        "workflow_id": r.workflow_id,
                        "efficiency_score": r.efficiency_score,
                        "workflow_type": r.workflow_type.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_efficiency_score(self) -> list[dict[str, Any]]:
        """Group by team, total efficiency_score, sort descending."""
        team_scores: dict[str, float] = {}
        for r in self._records:
            team_scores[r.team] = team_scores.get(r.team, 0) + r.efficiency_score
        results: list[dict[str, Any]] = []
        for team, total in team_scores.items():
            results.append(
                {
                    "team": team,
                    "total_efficiency": total,
                }
            )
        results.sort(key=lambda x: x["total_efficiency"], reverse=True)
        return results

    def detect_workflow_bottlenecks(self) -> dict[str, Any]:
        """Split-half on efficiency_score; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [r.efficiency_score for r in self._records]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> WorkflowEfficiencyReport:
        by_type: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_bottleneck: dict[str, int] = {}
        for r in self._records:
            by_type[r.workflow_type.value] = by_type.get(r.workflow_type.value, 0) + 1
            by_level[r.efficiency_level.value] = by_level.get(r.efficiency_level.value, 0) + 1
            by_bottleneck[r.bottleneck_type.value] = (
                by_bottleneck.get(r.bottleneck_type.value, 0) + 1
            )
        inefficient_count = sum(
            1 for r in self._records if r.efficiency_score < self._min_efficiency_score
        )
        efficient_workflows = len(
            {
                r.workflow_id
                for r in self._records
                if r.efficiency_score >= self._min_efficiency_score
            }
        )
        avg_eff = (
            round(sum(r.efficiency_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        inefficient_ids = [
            r.workflow_id for r in self._records if r.efficiency_score < self._min_efficiency_score
        ][:5]
        recs: list[str] = []
        if inefficient_count > 0:
            recs.append(
                f"{inefficient_count} workflow(s) below minimum efficiency"
                f" ({self._min_efficiency_score})"
            )
        if self._records and avg_eff < self._min_efficiency_score:
            recs.append(
                f"Average efficiency {avg_eff} is below threshold ({self._min_efficiency_score})"
            )
        if not recs:
            recs.append("Workflow efficiency levels are healthy")
        return WorkflowEfficiencyReport(
            total_records=len(self._records),
            total_steps=len(self._steps),
            efficient_workflows=efficient_workflows,
            avg_efficiency_score=avg_eff,
            by_type=by_type,
            by_level=by_level,
            by_bottleneck=by_bottleneck,
            inefficient=inefficient_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._steps.clear()
        logger.info("workflow_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.workflow_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_steps": len(self._steps),
            "min_efficiency_score": self._min_efficiency_score,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_workflows": len({r.workflow_id for r in self._records}),
        }
