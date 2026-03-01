"""Escalation Path Analyzer — analyze escalation paths, detect bottlenecks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EscalationStage(StrEnum):
    L1_TRIAGE = "l1_triage"
    L2_INVESTIGATION = "l2_investigation"
    L3_SPECIALIST = "l3_specialist"
    L4_ENGINEERING = "l4_engineering"
    L5_MANAGEMENT = "l5_management"


class PathEfficiency(StrEnum):
    OPTIMAL = "optimal"
    EFFICIENT = "efficient"
    ADEQUATE = "adequate"
    INEFFICIENT = "inefficient"
    BROKEN = "broken"


class BottleneckType(StrEnum):
    SKILL_GAP = "skill_gap"
    AVAILABILITY = "availability"
    PROCESS = "process"
    TOOLING = "tooling"
    COMMUNICATION = "communication"


# --- Models ---


class EscalationPathRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    path_id: str = ""
    escalation_stage: EscalationStage = EscalationStage.L1_TRIAGE
    path_efficiency: PathEfficiency = PathEfficiency.ADEQUATE
    bottleneck_type: BottleneckType = BottleneckType.PROCESS
    resolution_time_minutes: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PathMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    path_id: str = ""
    escalation_stage: EscalationStage = EscalationStage.L1_TRIAGE
    metric_value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EscalationPathReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    inefficient_paths: int = 0
    avg_resolution_time: float = 0.0
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_efficiency: dict[str, int] = Field(default_factory=dict)
    by_bottleneck: dict[str, int] = Field(default_factory=dict)
    top_bottlenecks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class EscalationPathAnalyzer:
    """Analyze escalation paths, detect bottlenecks, optimize routing."""

    def __init__(
        self,
        max_records: int = 200000,
        max_resolution_time_minutes: float = 120.0,
    ) -> None:
        self._max_records = max_records
        self._max_resolution_time_minutes = max_resolution_time_minutes
        self._records: list[EscalationPathRecord] = []
        self._metrics: list[PathMetric] = []
        logger.info(
            "escalation_path.initialized",
            max_records=max_records,
            max_resolution_time_minutes=max_resolution_time_minutes,
        )

    # -- record / get / list ------------------------------------------------

    def record_path(
        self,
        path_id: str,
        escalation_stage: EscalationStage = EscalationStage.L1_TRIAGE,
        path_efficiency: PathEfficiency = PathEfficiency.ADEQUATE,
        bottleneck_type: BottleneckType = BottleneckType.PROCESS,
        resolution_time_minutes: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> EscalationPathRecord:
        record = EscalationPathRecord(
            path_id=path_id,
            escalation_stage=escalation_stage,
            path_efficiency=path_efficiency,
            bottleneck_type=bottleneck_type,
            resolution_time_minutes=resolution_time_minutes,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "escalation_path.path_recorded",
            record_id=record.id,
            path_id=path_id,
            escalation_stage=escalation_stage.value,
            path_efficiency=path_efficiency.value,
        )
        return record

    def get_path(self, record_id: str) -> EscalationPathRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_paths(
        self,
        stage: EscalationStage | None = None,
        efficiency: PathEfficiency | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[EscalationPathRecord]:
        results = list(self._records)
        if stage is not None:
            results = [r for r in results if r.escalation_stage == stage]
        if efficiency is not None:
            results = [r for r in results if r.path_efficiency == efficiency]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        path_id: str,
        escalation_stage: EscalationStage = EscalationStage.L1_TRIAGE,
        metric_value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PathMetric:
        metric = PathMetric(
            path_id=path_id,
            escalation_stage=escalation_stage,
            metric_value=metric_value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "escalation_path.metric_added",
            path_id=path_id,
            escalation_stage=escalation_stage.value,
            metric_value=metric_value,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_path_efficiency(self) -> dict[str, Any]:
        """Group by escalation stage; return count and avg resolution time."""
        stage_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.escalation_stage.value
            stage_data.setdefault(key, []).append(r.resolution_time_minutes)
        result: dict[str, Any] = {}
        for stage, times in stage_data.items():
            result[stage] = {
                "count": len(times),
                "avg_resolution_time": round(sum(times) / len(times), 2),
            }
        return result

    def identify_inefficient_paths(self) -> list[dict[str, Any]]:
        """Return records where efficiency is INEFFICIENT or BROKEN."""
        inefficient_set = {PathEfficiency.INEFFICIENT, PathEfficiency.BROKEN}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.path_efficiency in inefficient_set:
                results.append(
                    {
                        "record_id": r.id,
                        "path_id": r.path_id,
                        "escalation_stage": r.escalation_stage.value,
                        "path_efficiency": r.path_efficiency.value,
                        "bottleneck_type": r.bottleneck_type.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_resolution_time(self) -> list[dict[str, Any]]:
        """Group by service, avg resolution time, sort descending."""
        svc_times: dict[str, list[float]] = {}
        for r in self._records:
            svc_times.setdefault(r.service, []).append(r.resolution_time_minutes)
        results: list[dict[str, Any]] = []
        for service, times in svc_times.items():
            results.append(
                {
                    "service": service,
                    "avg_resolution_time": round(sum(times) / len(times), 2),
                    "path_count": len(times),
                }
            )
        results.sort(key=lambda x: x["avg_resolution_time"], reverse=True)
        return results

    def detect_efficiency_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_value; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [m.metric_value for m in self._metrics]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> EscalationPathReport:
        by_stage: dict[str, int] = {}
        by_efficiency: dict[str, int] = {}
        by_bottleneck: dict[str, int] = {}
        for r in self._records:
            by_stage[r.escalation_stage.value] = by_stage.get(r.escalation_stage.value, 0) + 1
            by_efficiency[r.path_efficiency.value] = (
                by_efficiency.get(r.path_efficiency.value, 0) + 1
            )
            by_bottleneck[r.bottleneck_type.value] = (
                by_bottleneck.get(r.bottleneck_type.value, 0) + 1
            )
        inefficient_paths = sum(
            1
            for r in self._records
            if r.path_efficiency in {PathEfficiency.INEFFICIENT, PathEfficiency.BROKEN}
        )
        avg_resolution = (
            round(sum(r.resolution_time_minutes for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_resolution_time()
        top_bottlenecks = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if inefficient_paths > 0:
            recs.append(
                f"{inefficient_paths} inefficient path(s) detected — review escalation routing"
            )
        if avg_resolution > self._max_resolution_time_minutes:
            recs.append(
                f"Avg resolution time {avg_resolution}min exceeds "
                f"threshold ({self._max_resolution_time_minutes}min)"
            )
        if not recs:
            recs.append("Escalation path efficiency levels are healthy")
        return EscalationPathReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            inefficient_paths=inefficient_paths,
            avg_resolution_time=avg_resolution,
            by_stage=by_stage,
            by_efficiency=by_efficiency,
            by_bottleneck=by_bottleneck,
            top_bottlenecks=top_bottlenecks,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("escalation_path.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        stage_dist: dict[str, int] = {}
        for r in self._records:
            key = r.escalation_stage.value
            stage_dist[key] = stage_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "max_resolution_time_minutes": self._max_resolution_time_minutes,
            "stage_distribution": stage_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
