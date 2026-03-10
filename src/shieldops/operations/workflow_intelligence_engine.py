"""Workflow Intelligence Engine — workflow analysis and optimization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WorkflowComplexity(StrEnum):
    LINEAR = "linear"
    BRANCHING = "branching"
    PARALLEL = "parallel"
    ADAPTIVE = "adaptive"


class ExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class OptimizationGoal(StrEnum):
    SPEED = "speed"
    RELIABILITY = "reliability"
    COST = "cost"
    COVERAGE = "coverage"


# --- Models ---


class WorkflowRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    workflow_complexity: WorkflowComplexity = WorkflowComplexity.LINEAR
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    optimization_goal: OptimizationGoal = OptimizationGoal.RELIABILITY
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkflowAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    workflow_complexity: WorkflowComplexity = WorkflowComplexity.LINEAR
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkflowIntelligenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_workflow_complexity: dict[str, int] = Field(default_factory=dict)
    by_execution_status: dict[str, int] = Field(default_factory=dict)
    by_optimization_goal: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class WorkflowIntelligenceEngine:
    """Workflow Intelligence Engine
    for workflow analysis and optimization.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[WorkflowRecord] = []
        self._analyses: list[WorkflowAnalysis] = []
        logger.info(
            "workflow_intelligence_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def record_item(
        self,
        name: str,
        workflow_complexity: WorkflowComplexity = (WorkflowComplexity.LINEAR),
        execution_status: ExecutionStatus = (ExecutionStatus.PENDING),
        optimization_goal: OptimizationGoal = (OptimizationGoal.RELIABILITY),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> WorkflowRecord:
        record = WorkflowRecord(
            name=name,
            workflow_complexity=workflow_complexity,
            execution_status=execution_status,
            optimization_goal=optimization_goal,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "workflow_intelligence_engine.item_recorded",
            record_id=record.id,
            name=name,
        )
        return record

    def get_record(self, record_id: str) -> WorkflowRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        workflow_complexity: WorkflowComplexity | None = None,
        execution_status: ExecutionStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowRecord]:
        results = list(self._records)
        if workflow_complexity is not None:
            results = [r for r in results if r.workflow_complexity == workflow_complexity]
        if execution_status is not None:
            results = [r for r in results if r.execution_status == execution_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        workflow_complexity: WorkflowComplexity = (WorkflowComplexity.LINEAR),
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> WorkflowAnalysis:
        analysis = WorkflowAnalysis(
            name=name,
            workflow_complexity=workflow_complexity,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "workflow_intelligence_engine.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------

    def analyze_workflow_bottlenecks(
        self,
    ) -> list[dict[str, Any]]:
        """Identify bottlenecks in workflow execution."""
        results: list[dict[str, Any]] = []
        svc_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            svc_data.setdefault(r.service, []).append(
                {
                    "score": r.score,
                    "status": r.execution_status.value,
                    "complexity": r.workflow_complexity.value,
                }
            )
        for svc, entries in svc_data.items():
            failed = sum(1 for e in entries if e["status"] == "failed")
            avg_score = round(sum(e["score"] for e in entries) / len(entries), 2)
            results.append(
                {
                    "service": svc,
                    "total_workflows": len(entries),
                    "failed_count": failed,
                    "failure_rate": round(failed / len(entries) * 100, 2),
                    "avg_score": avg_score,
                    "is_bottleneck": (failed / len(entries) > 0.3 or avg_score < self._threshold),
                }
            )
        results.sort(key=lambda x: x["failure_rate"], reverse=True)
        return results

    def recommend_workflow_improvements(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend improvements for workflows."""
        recs: list[dict[str, Any]] = []
        complexity_scores: dict[str, list[float]] = {}
        for r in self._records:
            complexity_scores.setdefault(r.workflow_complexity.value, []).append(r.score)
        for comp, scores in complexity_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            if avg < self._threshold:
                recs.append(
                    {
                        "complexity_type": comp,
                        "avg_score": avg,
                        "recommendation": (f"Simplify {comp} workflows (avg score {avg})"),
                        "priority": "high" if avg < self._threshold * 0.5 else "medium",
                    }
                )
        recs.sort(key=lambda x: x["avg_score"])
        return recs

    def compute_workflow_efficiency(
        self,
    ) -> dict[str, Any]:
        """Compute overall workflow efficiency metrics."""
        if not self._records:
            return {
                "overall_efficiency": 0.0,
                "by_goal": {},
                "total_workflows": 0,
            }
        goal_data: dict[str, list[float]] = {}
        for r in self._records:
            goal_data.setdefault(r.optimization_goal.value, []).append(r.score)
        by_goal: dict[str, Any] = {}
        for goal, scores in goal_data.items():
            by_goal[goal] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        all_scores = [r.score for r in self._records]
        return {
            "overall_efficiency": round(sum(all_scores) / len(all_scores), 2),
            "by_goal": by_goal,
            "total_workflows": len(self._records),
        }

    # -- report / stats -----------------------------------------------

    def generate_report(self) -> WorkflowIntelligenceReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.workflow_complexity.value] = by_e1.get(r.workflow_complexity.value, 0) + 1
            by_e2[r.execution_status.value] = by_e2.get(r.execution_status.value, 0) + 1
            by_e3[r.optimization_goal.value] = by_e3.get(r.optimization_goal.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps = [r.name for r in self._records if r.score < self._threshold][:5]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Workflow Intelligence Engine is healthy")
        return WorkflowIntelligenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_workflow_complexity=by_e1,
            by_execution_status=by_e2,
            by_optimization_goal=by_e3,
            top_gaps=gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("workflow_intelligence_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.workflow_complexity.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "workflow_complexity_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
