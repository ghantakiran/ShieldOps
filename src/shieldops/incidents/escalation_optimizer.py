"""Escalation Path Optimizer — optimize escalation routing."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EscalationPath(StrEnum):
    DIRECT_TEAM = "direct_team"
    MANAGER_FIRST = "manager_first"
    CROSS_TEAM = "cross_team"
    EXECUTIVE = "executive"
    AUTOMATED = "automated"


class PathEfficiency(StrEnum):
    OPTIMAL = "optimal"
    EFFICIENT = "efficient"
    ADEQUATE = "adequate"
    SLOW = "slow"
    INEFFICIENT = "inefficient"


class OptimizationAction(StrEnum):
    SKIP_TIER = "skip_tier"
    PARALLEL_NOTIFY = "parallel_notify"
    AUTO_ROUTE = "auto_route"
    ADD_RESPONDER = "add_responder"
    NO_CHANGE = "no_change"


# --- Models ---


class EscalationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    path: EscalationPath = EscalationPath.DIRECT_TEAM
    efficiency: PathEfficiency = PathEfficiency.ADEQUATE
    resolution_time_minutes: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PathRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recommendation_name: str = ""
    path: EscalationPath = EscalationPath.DIRECT_TEAM
    action: OptimizationAction = OptimizationAction.NO_CHANGE
    time_saved_minutes: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EscalationOptimizerReport(BaseModel):
    total_records: int = 0
    total_recommendations: int = 0
    avg_resolution_time_min: float = 0.0
    by_path: dict[str, int] = Field(default_factory=dict)
    by_efficiency: dict[str, int] = Field(default_factory=dict)
    slow_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentEscalationOptimizer:
    """Optimize escalation routing based on historical patterns and outcomes."""

    def __init__(
        self,
        max_records: int = 200000,
        max_escalation_time_min: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._max_escalation_time_min = max_escalation_time_min
        self._records: list[EscalationRecord] = []
        self._recommendations: list[PathRecommendation] = []
        logger.info(
            "escalation_optimizer.initialized",
            max_records=max_records,
            max_escalation_time_min=max_escalation_time_min,
        )

    # -- record / get / list ---------------------------------------------

    def record_escalation(
        self,
        service_name: str,
        path: EscalationPath = EscalationPath.DIRECT_TEAM,
        efficiency: PathEfficiency = PathEfficiency.ADEQUATE,
        resolution_time_minutes: float = 0.0,
        details: str = "",
    ) -> EscalationRecord:
        record = EscalationRecord(
            service_name=service_name,
            path=path,
            efficiency=efficiency,
            resolution_time_minutes=resolution_time_minutes,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "escalation_optimizer.recorded",
            record_id=record.id,
            service_name=service_name,
            path=path.value,
            efficiency=efficiency.value,
        )
        return record

    def get_escalation(self, record_id: str) -> EscalationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_escalations(
        self,
        service_name: str | None = None,
        path: EscalationPath | None = None,
        limit: int = 50,
    ) -> list[EscalationRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if path is not None:
            results = [r for r in results if r.path == path]
        return results[-limit:]

    def add_recommendation(
        self,
        recommendation_name: str,
        path: EscalationPath = EscalationPath.DIRECT_TEAM,
        action: OptimizationAction = OptimizationAction.NO_CHANGE,
        time_saved_minutes: float = 0.0,
        description: str = "",
    ) -> PathRecommendation:
        rec = PathRecommendation(
            recommendation_name=recommendation_name,
            path=path,
            action=action,
            time_saved_minutes=time_saved_minutes,
            description=description,
        )
        self._recommendations.append(rec)
        if len(self._recommendations) > self._max_records:
            self._recommendations = self._recommendations[-self._max_records :]
        logger.info(
            "escalation_optimizer.recommendation_added",
            recommendation_name=recommendation_name,
            path=path.value,
            action=action.value,
        )
        return rec

    # -- domain operations -----------------------------------------------

    def analyze_escalation_efficiency(self, service_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_time = round(sum(r.resolution_time_minutes for r in records) / len(records), 2)
        slow = sum(
            1 for r in records if r.efficiency in (PathEfficiency.SLOW, PathEfficiency.INEFFICIENT)
        )
        return {
            "service_name": service_name,
            "total_records": len(records),
            "avg_resolution_time_min": avg_time,
            "slow_count": slow,
            "meets_threshold": avg_time <= self._max_escalation_time_min,
        }

    def identify_slow_escalations(self) -> list[dict[str, Any]]:
        slow_counts: dict[str, int] = {}
        for r in self._records:
            if r.efficiency in (PathEfficiency.SLOW, PathEfficiency.INEFFICIENT):
                slow_counts[r.service_name] = slow_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in slow_counts.items():
            if count > 1:
                results.append({"service_name": svc, "slow_count": count})
        results.sort(key=lambda x: x["slow_count"], reverse=True)
        return results

    def rank_by_resolution_time(self) -> list[dict[str, Any]]:
        svc_times: dict[str, list[float]] = {}
        for r in self._records:
            svc_times.setdefault(r.service_name, []).append(r.resolution_time_minutes)
        results: list[dict[str, Any]] = []
        for svc, times in svc_times.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_resolution_time_min": round(sum(times) / len(times), 2),
                    "record_count": len(times),
                }
            )
        results.sort(key=lambda x: x["avg_resolution_time_min"], reverse=True)
        return results

    def detect_escalation_patterns(self) -> list[dict[str, Any]]:
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "escalation_count": count,
                        "recurring": True,
                    }
                )
        results.sort(key=lambda x: x["escalation_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> EscalationOptimizerReport:
        by_path: dict[str, int] = {}
        by_efficiency: dict[str, int] = {}
        for r in self._records:
            by_path[r.path.value] = by_path.get(r.path.value, 0) + 1
            by_efficiency[r.efficiency.value] = by_efficiency.get(r.efficiency.value, 0) + 1
        avg_time = (
            round(
                sum(r.resolution_time_minutes for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        slow_count = sum(
            1
            for r in self._records
            if r.efficiency in (PathEfficiency.SLOW, PathEfficiency.INEFFICIENT)
        )
        recs: list[str] = []
        if avg_time > self._max_escalation_time_min:
            recs.append(
                f"Avg resolution time {avg_time}min exceeds "
                f"{self._max_escalation_time_min}min threshold"
            )
        recurring = len(self.detect_escalation_patterns())
        if recurring > 0:
            recs.append(f"{recurring} service(s) with recurring escalation patterns")
        if not recs:
            recs.append("Escalation optimization meets targets")
        return EscalationOptimizerReport(
            total_records=len(self._records),
            total_recommendations=len(self._recommendations),
            avg_resolution_time_min=avg_time,
            by_path=by_path,
            by_efficiency=by_efficiency,
            slow_count=slow_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._recommendations.clear()
        logger.info("escalation_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        path_dist: dict[str, int] = {}
        for r in self._records:
            key = r.path.value
            path_dist[key] = path_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_recommendations": len(self._recommendations),
            "max_escalation_time_min": self._max_escalation_time_min,
            "path_distribution": path_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
