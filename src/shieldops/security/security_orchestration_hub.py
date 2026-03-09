"""Security Orchestration Hub — cross-tool orchestration, workflow chaining, conditional routing."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class OrchestrationAction(StrEnum):
    ENRICH = "enrich"
    CONTAIN = "contain"
    INVESTIGATE = "investigate"
    REMEDIATE = "remediate"
    NOTIFY = "notify"


class RoutingCondition(StrEnum):
    SEVERITY_BASED = "severity_based"
    SOURCE_BASED = "source_based"
    ASSET_BASED = "asset_based"
    TIME_BASED = "time_based"
    CONTEXT_BASED = "context_based"


class WorkflowChainStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"
    CANCELLED = "cancelled"


# --- Models ---


class OrchestrationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str = ""
    action: OrchestrationAction = OrchestrationAction.ENRICH
    routing_condition: RoutingCondition = RoutingCondition.SEVERITY_BASED
    chain_status: WorkflowChainStatus = WorkflowChainStatus.RUNNING
    execution_time_sec: float = 0.0
    steps_completed: int = 0
    steps_total: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class OrchestrationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str = ""
    action: OrchestrationAction = OrchestrationAction.ENRICH
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OrchestrationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_execution_time: float = 0.0
    completion_rate: float = 0.0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_routing: dict[str, int] = Field(default_factory=dict)
    by_chain_status: dict[str, int] = Field(default_factory=dict)
    slow_workflows: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SecurityOrchestrationHub:
    """Cross-tool orchestration, workflow chaining, conditional routing, response coordination."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 120.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[OrchestrationRecord] = []
        self._analyses: list[OrchestrationAnalysis] = []
        logger.info(
            "security_orchestration_hub.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def add_record(
        self,
        workflow_name: str,
        action: OrchestrationAction = OrchestrationAction.ENRICH,
        routing_condition: RoutingCondition = RoutingCondition.SEVERITY_BASED,
        chain_status: WorkflowChainStatus = WorkflowChainStatus.RUNNING,
        execution_time_sec: float = 0.0,
        steps_completed: int = 0,
        steps_total: int = 0,
        service: str = "",
        team: str = "",
    ) -> OrchestrationRecord:
        record = OrchestrationRecord(
            workflow_name=workflow_name,
            action=action,
            routing_condition=routing_condition,
            chain_status=chain_status,
            execution_time_sec=execution_time_sec,
            steps_completed=steps_completed,
            steps_total=steps_total,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "security_orchestration_hub.record_added",
            record_id=record.id,
            workflow_name=workflow_name,
            action=action.value,
        )
        return record

    def get_record(self, record_id: str) -> OrchestrationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        action: OrchestrationAction | None = None,
        chain_status: WorkflowChainStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[OrchestrationRecord]:
        results = list(self._records)
        if action is not None:
            results = [r for r in results if r.action == action]
        if chain_status is not None:
            results = [r for r in results if r.chain_status == chain_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        workflow_name: str,
        action: OrchestrationAction = OrchestrationAction.ENRICH,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> OrchestrationAnalysis:
        analysis = OrchestrationAnalysis(
            workflow_name=workflow_name,
            action=action,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "security_orchestration_hub.analysis_added",
            workflow_name=workflow_name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_workflow_performance(self) -> list[dict[str, Any]]:
        wf_data: dict[str, list[OrchestrationRecord]] = {}
        for r in self._records:
            wf_data.setdefault(r.workflow_name, []).append(r)
        results: list[dict[str, Any]] = []
        for wf, records in wf_data.items():
            times = [r.execution_time_sec for r in records]
            completed = sum(1 for r in records if r.chain_status == WorkflowChainStatus.COMPLETED)
            failed = sum(1 for r in records if r.chain_status == WorkflowChainStatus.FAILED)
            total = len(records)
            results.append(
                {
                    "workflow_name": wf,
                    "avg_execution_time": round(sum(times) / len(times), 2),
                    "completion_rate": round(completed / total * 100, 2) if total else 0,
                    "failure_rate": round(failed / total * 100, 2) if total else 0,
                    "total_executions": total,
                }
            )
        return sorted(results, key=lambda x: x["avg_execution_time"], reverse=True)

    def evaluate_routing_effectiveness(self) -> dict[str, Any]:
        route_data: dict[str, dict[str, int]] = {}
        for r in self._records:
            key = r.routing_condition.value
            route_data.setdefault(key, {"completed": 0, "failed": 0, "total": 0})
            route_data[key]["total"] += 1
            if r.chain_status == WorkflowChainStatus.COMPLETED:
                route_data[key]["completed"] += 1
            elif r.chain_status == WorkflowChainStatus.FAILED:
                route_data[key]["failed"] += 1
        results: dict[str, Any] = {}
        for route, counts in route_data.items():
            results[route] = {
                "success_rate": round(counts["completed"] / counts["total"] * 100, 2)
                if counts["total"]
                else 0,
                "total": counts["total"],
            }
        return results

    def identify_slow_workflows(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.execution_time_sec > self._threshold:
                results.append(
                    {
                        "workflow_name": r.workflow_name,
                        "execution_time_sec": r.execution_time_sec,
                        "steps_completed": r.steps_completed,
                        "steps_total": r.steps_total,
                        "action": r.action.value,
                    }
                )
        return sorted(results, key=lambda x: x["execution_time_sec"], reverse=True)

    def compute_step_completion(self) -> dict[str, Any]:
        if not self._records:
            return {"avg_completion_pct": 0.0, "total_workflows": 0}
        completion_pcts: list[float] = []
        for r in self._records:
            if r.steps_total > 0:
                completion_pcts.append(r.steps_completed / r.steps_total * 100)
        avg_pct = round(sum(completion_pcts) / len(completion_pcts), 2) if completion_pcts else 0.0
        return {
            "avg_completion_pct": avg_pct,
            "fully_completed": sum(1 for p in completion_pcts if p >= 100),
            "total_workflows": len(self._records),
        }

    def detect_trends(self) -> dict[str, Any]:
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

    def process(self, workflow_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.workflow_name == workflow_name]
        if not matching:
            return {"workflow_name": workflow_name, "status": "no_data"}
        times = [r.execution_time_sec for r in matching]
        completed = sum(1 for r in matching if r.chain_status == WorkflowChainStatus.COMPLETED)
        return {
            "workflow_name": workflow_name,
            "total_executions": len(matching),
            "avg_execution_time": round(sum(times) / len(times), 2),
            "completion_rate": round(completed / len(matching) * 100, 2),
        }

    def generate_report(self) -> OrchestrationReport:
        by_act: dict[str, int] = {}
        by_rt: dict[str, int] = {}
        by_cs: dict[str, int] = {}
        for r in self._records:
            by_act[r.action.value] = by_act.get(r.action.value, 0) + 1
            by_rt[r.routing_condition.value] = by_rt.get(r.routing_condition.value, 0) + 1
            by_cs[r.chain_status.value] = by_cs.get(r.chain_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.execution_time_sec > self._threshold)
        times = [r.execution_time_sec for r in self._records]
        avg_time = round(sum(times) / len(times), 2) if times else 0.0
        completed = sum(1 for r in self._records if r.chain_status == WorkflowChainStatus.COMPLETED)
        total = len(self._records) or 1
        completion_rate = round(completed / total * 100, 2)
        slow = self.identify_slow_workflows()
        slow_names = [s["workflow_name"] for s in slow[:5]]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(f"{gap_count} workflow(s) exceeding time threshold ({self._threshold}s)")
        failed = by_cs.get("failed", 0)
        if failed > 0:
            recs.append(f"{failed} workflow(s) in failed state — investigate root causes")
        if completion_rate < 80.0:
            recs.append(f"Completion rate {completion_rate}% — target 80%+")
        if not recs:
            recs.append("Security orchestration hub is healthy")
        return OrchestrationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_execution_time=avg_time,
            completion_rate=completion_rate,
            by_action=by_act,
            by_routing=by_rt,
            by_chain_status=by_cs,
            slow_workflows=slow_names,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        act_dist: dict[str, int] = {}
        for r in self._records:
            key = r.action.value
            act_dist[key] = act_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "action_distribution": act_dist,
            "unique_workflows": len({r.workflow_name for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("security_orchestration_hub.cleared")
        return {"status": "cleared"}
