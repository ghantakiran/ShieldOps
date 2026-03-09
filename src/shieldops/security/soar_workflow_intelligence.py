"""SOAR Workflow Intelligence
playbook effectiveness, workflow optimization, bottleneck detection."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PlaybookStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    DEPRECATED = "deprecated"
    TESTING = "testing"
    FAILED = "failed"


class WorkflowStage(StrEnum):
    TRIAGE = "triage"
    ENRICHMENT = "enrichment"
    CONTAINMENT = "containment"
    ERADICATION = "eradication"
    RECOVERY = "recovery"


class BottleneckType(StrEnum):
    HUMAN_APPROVAL = "human_approval"
    API_TIMEOUT = "api_timeout"
    RESOURCE_CONTENTION = "resource_contention"
    DATA_DEPENDENCY = "data_dependency"
    RATE_LIMIT = "rate_limit"


# --- Models ---


class WorkflowRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    playbook_name: str = ""
    playbook_status: PlaybookStatus = PlaybookStatus.ACTIVE
    workflow_stage: WorkflowStage = WorkflowStage.TRIAGE
    bottleneck_type: BottleneckType = BottleneckType.HUMAN_APPROVAL
    execution_time_sec: float = 0.0
    automation_pct: float = 0.0
    success_rate: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class WorkflowAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    playbook_name: str = ""
    workflow_stage: WorkflowStage = WorkflowStage.TRIAGE
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
    avg_execution_time: float = 0.0
    avg_automation_pct: float = 0.0
    avg_success_rate: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_bottleneck: dict[str, int] = Field(default_factory=dict)
    top_bottlenecks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SoarWorkflowIntelligence:
    """Playbook effectiveness analysis, workflow optimization, bottleneck detection."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[WorkflowRecord] = []
        self._analyses: list[WorkflowAnalysis] = []
        logger.info(
            "soar_workflow_intelligence.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def add_record(
        self,
        playbook_name: str,
        playbook_status: PlaybookStatus = PlaybookStatus.ACTIVE,
        workflow_stage: WorkflowStage = WorkflowStage.TRIAGE,
        bottleneck_type: BottleneckType = BottleneckType.HUMAN_APPROVAL,
        execution_time_sec: float = 0.0,
        automation_pct: float = 0.0,
        success_rate: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> WorkflowRecord:
        record = WorkflowRecord(
            playbook_name=playbook_name,
            playbook_status=playbook_status,
            workflow_stage=workflow_stage,
            bottleneck_type=bottleneck_type,
            execution_time_sec=execution_time_sec,
            automation_pct=automation_pct,
            success_rate=success_rate,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "soar_workflow_intelligence.record_added",
            record_id=record.id,
            playbook_name=playbook_name,
            workflow_stage=workflow_stage.value,
        )
        return record

    def get_record(self, record_id: str) -> WorkflowRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        playbook_status: PlaybookStatus | None = None,
        workflow_stage: WorkflowStage | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[WorkflowRecord]:
        results = list(self._records)
        if playbook_status is not None:
            results = [r for r in results if r.playbook_status == playbook_status]
        if workflow_stage is not None:
            results = [r for r in results if r.workflow_stage == workflow_stage]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        playbook_name: str,
        workflow_stage: WorkflowStage = WorkflowStage.TRIAGE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> WorkflowAnalysis:
        analysis = WorkflowAnalysis(
            playbook_name=playbook_name,
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
            "soar_workflow_intelligence.analysis_added",
            playbook_name=playbook_name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def detect_bottlenecks(self) -> list[dict[str, Any]]:
        bottleneck_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.bottleneck_type.value
            bottleneck_data.setdefault(key, []).append(r.execution_time_sec)
        results: list[dict[str, Any]] = []
        for btype, times in bottleneck_data.items():
            avg_time = sum(times) / len(times)
            results.append(
                {
                    "bottleneck_type": btype,
                    "occurrence_count": len(times),
                    "avg_delay_sec": round(avg_time, 2),
                    "total_delay_sec": round(sum(times), 2),
                }
            )
        return sorted(results, key=lambda x: x["total_delay_sec"], reverse=True)

    def compute_automation_coverage(self) -> dict[str, Any]:
        if not self._records:
            return {"avg_automation_pct": 0.0, "fully_automated": 0, "total": 0}
        auto_pcts = [r.automation_pct for r in self._records]
        fully_auto = sum(1 for r in self._records if r.automation_pct >= 90.0)
        low_auto = sum(1 for r in self._records if r.automation_pct < 30.0)
        return {
            "avg_automation_pct": round(sum(auto_pcts) / len(auto_pcts), 2),
            "fully_automated": fully_auto,
            "low_automation": low_auto,
            "total": len(self._records),
        }

    def rank_playbooks(self) -> list[dict[str, Any]]:
        pb_data: dict[str, list[WorkflowRecord]] = {}
        for r in self._records:
            pb_data.setdefault(r.playbook_name, []).append(r)
        results: list[dict[str, Any]] = []
        for pb, records in pb_data.items():
            successes = [r.success_rate for r in records]
            times = [r.execution_time_sec for r in records]
            results.append(
                {
                    "playbook_name": pb,
                    "avg_success_rate": round(sum(successes) / len(successes), 2),
                    "avg_execution_time": round(sum(times) / len(times), 2),
                    "execution_count": len(records),
                }
            )
        results.sort(key=lambda x: x["avg_success_rate"])
        return results

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

    def process(self, playbook_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.playbook_name == playbook_name]
        if not matching:
            return {"playbook_name": playbook_name, "status": "no_data"}
        successes = [r.success_rate for r in matching]
        times = [r.execution_time_sec for r in matching]
        return {
            "playbook_name": playbook_name,
            "executions": len(matching),
            "avg_success_rate": round(sum(successes) / len(successes), 2),
            "avg_execution_time": round(sum(times) / len(times), 2),
        }

    def generate_report(self) -> WorkflowIntelligenceReport:
        by_st: dict[str, int] = {}
        by_sg: dict[str, int] = {}
        by_bn: dict[str, int] = {}
        for r in self._records:
            by_st[r.playbook_status.value] = by_st.get(r.playbook_status.value, 0) + 1
            by_sg[r.workflow_stage.value] = by_sg.get(r.workflow_stage.value, 0) + 1
            by_bn[r.bottleneck_type.value] = by_bn.get(r.bottleneck_type.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.success_rate < self._threshold)
        times = [r.execution_time_sec for r in self._records]
        avg_time = round(sum(times) / len(times), 2) if times else 0.0
        auto_pcts = [r.automation_pct for r in self._records]
        avg_auto = round(sum(auto_pcts) / len(auto_pcts), 2) if auto_pcts else 0.0
        sr = [r.success_rate for r in self._records]
        avg_sr = round(sum(sr) / len(sr), 2) if sr else 0.0
        bottlenecks = self.detect_bottlenecks()
        top_bn = [b["bottleneck_type"] for b in bottlenecks[:5]]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(f"{gap_count} playbook(s) below success threshold ({self._threshold}%)")
        if avg_auto < 50.0:
            recs.append(f"Low avg automation ({avg_auto}%) — increase automated steps")
        if top_bn:
            recs.append(f"Top bottlenecks: {', '.join(top_bn[:3])}")
        if not recs:
            recs.append("SOAR workflow intelligence is healthy")
        return WorkflowIntelligenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_execution_time=avg_time,
            avg_automation_pct=avg_auto,
            avg_success_rate=avg_sr,
            by_status=by_st,
            by_stage=by_sg,
            by_bottleneck=by_bn,
            top_bottlenecks=top_bn,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            key = r.workflow_stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "stage_distribution": stage_dist,
            "unique_playbooks": len({r.playbook_name for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("soar_workflow_intelligence.cleared")
        return {"status": "cleared"}
