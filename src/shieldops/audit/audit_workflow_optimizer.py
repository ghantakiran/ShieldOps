"""Audit Workflow Optimizer — optimize audit workflows, detect bottlenecks and long cycles."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WorkflowStage(StrEnum):
    EVIDENCE_COLLECTION = "evidence_collection"
    CONTROL_TESTING = "control_testing"
    FINDING_REVIEW = "finding_review"
    REMEDIATION_TRACKING = "remediation_tracking"
    REPORT_GENERATION = "report_generation"


class BottleneckType(StrEnum):
    MANUAL_HANDOFF = "manual_handoff"
    APPROVAL_DELAY = "approval_delay"
    EVIDENCE_GAP = "evidence_gap"
    RESOURCE_CONTENTION = "resource_contention"
    DEPENDENCY_WAIT = "dependency_wait"


class OptimizationType(StrEnum):
    PARALLELIZE = "parallelize"
    AUTOMATE = "automate"
    ELIMINATE = "eliminate"
    CONSOLIDATE = "consolidate"
    DEFER = "defer"


# --- Models ---


class WorkflowRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str = ""
    workflow_stage: WorkflowStage = WorkflowStage.EVIDENCE_COLLECTION
    bottleneck_type: BottleneckType = BottleneckType.MANUAL_HANDOFF
    optimization_type: OptimizationType = OptimizationType.PARALLELIZE
    cycle_time_hours: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkflowAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str = ""
    workflow_stage: WorkflowStage = WorkflowStage.EVIDENCE_COLLECTION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AuditWorkflowReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    long_cycle_count: int = 0
    avg_cycle_time: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_bottleneck: dict[str, int] = Field(default_factory=dict)
    by_optimization: dict[str, int] = Field(default_factory=dict)
    top_long_cycles: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AuditWorkflowOptimizer:
    """Optimize audit workflows, detect bottlenecks and long cycle times."""

    def __init__(
        self,
        max_records: int = 200000,
        cycle_time_threshold: float = 72.0,
    ) -> None:
        self._max_records = max_records
        self._cycle_time_threshold = cycle_time_threshold
        self._records: list[WorkflowRecord] = []
        self._analyses: list[WorkflowAnalysis] = []
        logger.info(
            "audit_workflow_optimizer.initialized",
            max_records=max_records,
            cycle_time_threshold=cycle_time_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_workflow(
        self,
        workflow_name: str,
        workflow_stage: WorkflowStage = WorkflowStage.EVIDENCE_COLLECTION,
        bottleneck_type: BottleneckType = BottleneckType.MANUAL_HANDOFF,
        optimization_type: OptimizationType = OptimizationType.PARALLELIZE,
        cycle_time_hours: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> WorkflowRecord:
        record = WorkflowRecord(
            workflow_name=workflow_name,
            workflow_stage=workflow_stage,
            bottleneck_type=bottleneck_type,
            optimization_type=optimization_type,
            cycle_time_hours=cycle_time_hours,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "audit_workflow_optimizer.workflow_recorded",
            record_id=record.id,
            workflow_name=workflow_name,
            workflow_stage=workflow_stage.value,
            bottleneck_type=bottleneck_type.value,
        )
        return record

    def get_workflow(self, record_id: str) -> WorkflowRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_workflows(
        self,
        workflow_stage: WorkflowStage | None = None,
        bottleneck_type: BottleneckType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowRecord]:
        results = list(self._records)
        if workflow_stage is not None:
            results = [r for r in results if r.workflow_stage == workflow_stage]
        if bottleneck_type is not None:
            results = [r for r in results if r.bottleneck_type == bottleneck_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        workflow_name: str,
        workflow_stage: WorkflowStage = WorkflowStage.EVIDENCE_COLLECTION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> WorkflowAnalysis:
        analysis = WorkflowAnalysis(
            workflow_name=workflow_name,
            workflow_stage=workflow_stage,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "audit_workflow_optimizer.analysis_added",
            workflow_name=workflow_name,
            workflow_stage=workflow_stage.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_workflow_distribution(self) -> dict[str, Any]:
        """Group by workflow_stage; return count and avg cycle_time_hours."""
        stage_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.workflow_stage.value
            stage_data.setdefault(key, []).append(r.cycle_time_hours)
        result: dict[str, Any] = {}
        for stage, times in stage_data.items():
            result[stage] = {
                "count": len(times),
                "avg_cycle_time": round(sum(times) / len(times), 2),
            }
        return result

    def identify_long_cycle_workflows(self) -> list[dict[str, Any]]:
        """Return records where cycle_time_hours > cycle_time_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.cycle_time_hours > self._cycle_time_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "workflow_name": r.workflow_name,
                        "workflow_stage": r.workflow_stage.value,
                        "cycle_time_hours": r.cycle_time_hours,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["cycle_time_hours"], reverse=True)

    def rank_by_cycle_time(self) -> list[dict[str, Any]]:
        """Group by service, avg cycle_time_hours, sort descending."""
        svc_times: dict[str, list[float]] = {}
        for r in self._records:
            svc_times.setdefault(r.service, []).append(r.cycle_time_hours)
        results: list[dict[str, Any]] = []
        for svc, times in svc_times.items():
            results.append(
                {
                    "service": svc,
                    "avg_cycle_time": round(sum(times) / len(times), 2),
                }
            )
        results.sort(key=lambda x: x["avg_cycle_time"], reverse=True)
        return results

    def detect_workflow_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> AuditWorkflowReport:
        by_stage: dict[str, int] = {}
        by_bottleneck: dict[str, int] = {}
        by_optimization: dict[str, int] = {}
        for r in self._records:
            by_stage[r.workflow_stage.value] = by_stage.get(r.workflow_stage.value, 0) + 1
            by_bottleneck[r.bottleneck_type.value] = (
                by_bottleneck.get(r.bottleneck_type.value, 0) + 1
            )
            by_optimization[r.optimization_type.value] = (
                by_optimization.get(r.optimization_type.value, 0) + 1
            )
        long_cycle_count = sum(
            1 for r in self._records if r.cycle_time_hours > self._cycle_time_threshold
        )
        times = [r.cycle_time_hours for r in self._records]
        avg_cycle_time = round(sum(times) / len(times), 2) if times else 0.0
        long_list = self.identify_long_cycle_workflows()
        top_long_cycles = [o["workflow_name"] for o in long_list[:5]]
        recs: list[str] = []
        if long_cycle_count > 0:
            recs.append(f"{long_cycle_count} long-cycle workflow(s) — optimize immediately")
        if self._records and avg_cycle_time > self._cycle_time_threshold:
            recs.append(
                f"Avg cycle time {avg_cycle_time}h exceeds threshold "
                f"({self._cycle_time_threshold}h)"
            )
        if not recs:
            recs.append("Audit workflow levels are healthy")
        return AuditWorkflowReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            long_cycle_count=long_cycle_count,
            avg_cycle_time=avg_cycle_time,
            by_stage=by_stage,
            by_bottleneck=by_bottleneck,
            by_optimization=by_optimization,
            top_long_cycles=top_long_cycles,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("audit_workflow_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            key = r.workflow_stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "cycle_time_threshold": self._cycle_time_threshold,
            "stage_distribution": stage_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
