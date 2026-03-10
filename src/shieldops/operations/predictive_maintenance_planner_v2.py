"""Predictive Maintenance Planner V2 — predictive maintenance with ML-driven scheduling."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MaintenanceType(StrEnum):
    PREVENTIVE = "preventive"
    PREDICTIVE = "predictive"
    CORRECTIVE = "corrective"
    EMERGENCY = "emergency"


class ComponentHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADING = "degrading"
    FAILING = "failing"
    FAILED = "failed"


class MaintenanceWindow(StrEnum):
    IMMEDIATE = "immediate"
    NEXT_WINDOW = "next_window"
    SCHEDULED = "scheduled"
    DEFERRED = "deferred"


# --- Models ---


class MaintenanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    maintenance_type: MaintenanceType = MaintenanceType.PREVENTIVE
    component_health: ComponentHealth = ComponentHealth.HEALTHY
    maintenance_window: MaintenanceWindow = MaintenanceWindow.SCHEDULED
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MaintenanceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    maintenance_type: MaintenanceType = MaintenanceType.PREVENTIVE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PredictiveMaintenanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_maintenance_type: dict[str, int] = Field(default_factory=dict)
    by_component_health: dict[str, int] = Field(default_factory=dict)
    by_maintenance_window: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PredictiveMaintenancePlannerV2:
    """Predictive Maintenance Planner V2
    for ML-driven maintenance scheduling.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[MaintenanceRecord] = []
        self._analyses: list[MaintenanceAnalysis] = []
        logger.info(
            "predictive_maintenance_planner_v2.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def record_item(
        self,
        name: str,
        maintenance_type: MaintenanceType = (MaintenanceType.PREVENTIVE),
        component_health: ComponentHealth = (ComponentHealth.HEALTHY),
        maintenance_window: MaintenanceWindow = (MaintenanceWindow.SCHEDULED),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MaintenanceRecord:
        record = MaintenanceRecord(
            name=name,
            maintenance_type=maintenance_type,
            component_health=component_health,
            maintenance_window=maintenance_window,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "predictive_maintenance_planner_v2.item_recorded",
            record_id=record.id,
            name=name,
        )
        return record

    def get_record(self, record_id: str) -> MaintenanceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        maintenance_type: MaintenanceType | None = None,
        component_health: ComponentHealth | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MaintenanceRecord]:
        results = list(self._records)
        if maintenance_type is not None:
            results = [r for r in results if r.maintenance_type == maintenance_type]
        if component_health is not None:
            results = [r for r in results if r.component_health == component_health]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        maintenance_type: MaintenanceType = (MaintenanceType.PREVENTIVE),
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MaintenanceAnalysis:
        analysis = MaintenanceAnalysis(
            name=name,
            maintenance_type=maintenance_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "predictive_maintenance_planner_v2.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------

    def predict_component_failure(self) -> list[dict[str, Any]]:
        """Predict component failures based on health trends."""
        results: list[dict[str, Any]] = []
        svc_health: dict[str, list[tuple[str, float]]] = {}
        for r in self._records:
            svc_health.setdefault(r.service, []).append((r.component_health.value, r.score))
        health_weight = {
            "healthy": 0.0,
            "degrading": 0.3,
            "failing": 0.7,
            "failed": 1.0,
        }
        for svc, entries in svc_health.items():
            risk_scores = [health_weight.get(h, 0.0) * (100 - s) / 100 for h, s in entries]
            avg_risk = round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0
            results.append(
                {
                    "service": svc,
                    "failure_risk": avg_risk,
                    "sample_count": len(entries),
                    "needs_attention": avg_risk > 0.5,
                }
            )
        results.sort(key=lambda x: x["failure_risk"], reverse=True)
        return results

    def optimize_maintenance_schedule(
        self,
    ) -> dict[str, Any]:
        """Optimize maintenance scheduling windows."""
        window_data: dict[str, list[float]] = {}
        for r in self._records:
            window_data.setdefault(r.maintenance_window.value, []).append(r.score)
        schedule: dict[str, Any] = {}
        for window, scores in window_data.items():
            avg = round(sum(scores) / len(scores), 2)
            schedule[window] = {
                "count": len(scores),
                "avg_effectiveness": avg,
                "recommended": avg >= self._threshold,
            }
        return {
            "window_analysis": schedule,
            "total_scheduled": len(self._records),
            "optimal_window": max(
                schedule,
                key=lambda w: schedule[w]["avg_effectiveness"],
            )
            if schedule
            else "scheduled",
        }

    def compute_maintenance_roi(self) -> dict[str, Any]:
        """Compute ROI of maintenance activities."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            type_data.setdefault(r.maintenance_type.value, []).append(r.score)
        roi: dict[str, Any] = {}
        for mtype, scores in type_data.items():
            avg = round(sum(scores) / len(scores), 2)
            cost_factor = {
                "preventive": 1.0,
                "predictive": 1.5,
                "corrective": 3.0,
                "emergency": 5.0,
            }.get(mtype, 1.0)
            roi[mtype] = {
                "avg_effectiveness": avg,
                "cost_factor": cost_factor,
                "roi_score": round(avg / cost_factor, 2),
            }
        return {
            "roi_by_type": roi,
            "total_activities": len(self._records),
        }

    # -- report / stats -----------------------------------------------

    def generate_report(self) -> PredictiveMaintenanceReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.maintenance_type.value] = by_e1.get(r.maintenance_type.value, 0) + 1
            by_e2[r.component_health.value] = by_e2.get(r.component_health.value, 0) + 1
            by_e3[r.maintenance_window.value] = by_e3.get(r.maintenance_window.value, 0) + 1
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
            recs.append("Predictive Maintenance Planner V2 is healthy")
        return PredictiveMaintenanceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_maintenance_type=by_e1,
            by_component_health=by_e2,
            by_maintenance_window=by_e3,
            top_gaps=gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("predictive_maintenance_planner_v2.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.maintenance_type.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "maintenance_type_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
