"""Containerization ROI Calculator — calculate ROI of containerization efforts."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WorkloadType(StrEnum):
    STATELESS = "stateless"
    STATEFUL = "stateful"
    BATCH = "batch"
    STREAMING = "streaming"
    ML_TRAINING = "ml_training"


class MigrationPhase(StrEnum):
    ASSESSMENT = "assessment"
    CONTAINERIZATION = "containerization"
    OPTIMIZATION = "optimization"
    SCALING = "scaling"
    COMPLETE = "complete"


class ROICategory(StrEnum):
    COMPUTE_SAVINGS = "compute_savings"
    OPERATIONAL = "operational"
    DEVELOPER_PRODUCTIVITY = "developer_productivity"
    SCALABILITY = "scalability"
    RESILIENCE = "resilience"


# --- Models ---


class ContainerizationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workload_type: WorkloadType = WorkloadType.STATELESS
    migration_phase: MigrationPhase = MigrationPhase.ASSESSMENT
    roi_category: ROICategory = ROICategory.COMPUTE_SAVINGS
    cost_before: float = 0.0
    cost_after: float = 0.0
    roi_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ROIAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workload_type: WorkloadType = WorkloadType.STATELESS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ContainerizationROIReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_roi_count: int = 0
    avg_roi_pct: float = 0.0
    by_workload_type: dict[str, int] = Field(default_factory=dict)
    by_migration_phase: dict[str, int] = Field(default_factory=dict)
    by_roi_category: dict[str, int] = Field(default_factory=dict)
    top_roi_workloads: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ContainerizationROICalculator:
    """Calculate and track ROI of containerization migrations."""

    def __init__(
        self,
        max_records: int = 200000,
        roi_threshold: float = 25.0,
    ) -> None:
        self._max_records = max_records
        self._roi_threshold = roi_threshold
        self._records: list[ContainerizationRecord] = []
        self._analyses: list[ROIAnalysis] = []
        logger.info(
            "containerization_roi_calculator.initialized",
            max_records=max_records,
            roi_threshold=roi_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_roi(
        self,
        workload_type: WorkloadType = WorkloadType.STATELESS,
        migration_phase: MigrationPhase = MigrationPhase.ASSESSMENT,
        roi_category: ROICategory = ROICategory.COMPUTE_SAVINGS,
        cost_before: float = 0.0,
        cost_after: float = 0.0,
        roi_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ContainerizationRecord:
        record = ContainerizationRecord(
            workload_type=workload_type,
            migration_phase=migration_phase,
            roi_category=roi_category,
            cost_before=cost_before,
            cost_after=cost_after,
            roi_pct=roi_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "containerization_roi_calculator.roi_recorded",
            record_id=record.id,
            workload_type=workload_type.value,
            roi_pct=roi_pct,
        )
        return record

    def get_roi(self, record_id: str) -> ContainerizationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_rois(
        self,
        workload_type: WorkloadType | None = None,
        migration_phase: MigrationPhase | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ContainerizationRecord]:
        results = list(self._records)
        if workload_type is not None:
            results = [r for r in results if r.workload_type == workload_type]
        if migration_phase is not None:
            results = [r for r in results if r.migration_phase == migration_phase]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        workload_type: WorkloadType = WorkloadType.STATELESS,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ROIAnalysis:
        analysis = ROIAnalysis(
            workload_type=workload_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "containerization_roi_calculator.analysis_added",
            workload_type=workload_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_workload_distribution(self) -> dict[str, Any]:
        """Group by workload_type; return count and avg roi_pct."""
        wl_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.workload_type.value
            wl_data.setdefault(key, []).append(r.roi_pct)
        result: dict[str, Any] = {}
        for wl, rois in wl_data.items():
            result[wl] = {
                "count": len(rois),
                "avg_roi_pct": round(sum(rois) / len(rois), 2),
            }
        return result

    def identify_high_roi_workloads(self) -> list[dict[str, Any]]:
        """Return records where roi_pct >= roi_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.roi_pct >= self._roi_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "workload_type": r.workload_type.value,
                        "roi_pct": r.roi_pct,
                        "cost_before": r.cost_before,
                        "cost_after": r.cost_after,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["roi_pct"], reverse=True)

    def rank_by_roi(self) -> list[dict[str, Any]]:
        """Group by service, avg roi_pct, sort descending."""
        svc_rois: dict[str, list[float]] = {}
        for r in self._records:
            svc_rois.setdefault(r.service, []).append(r.roi_pct)
        results: list[dict[str, Any]] = [
            {"service": svc, "avg_roi_pct": round(sum(r) / len(r), 2)}
            for svc, r in svc_rois.items()
        ]
        results.sort(key=lambda x: x["avg_roi_pct"], reverse=True)
        return results

    def detect_roi_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
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

    def generate_report(self) -> ContainerizationROIReport:
        by_workload: dict[str, int] = {}
        by_phase: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_workload[r.workload_type.value] = by_workload.get(r.workload_type.value, 0) + 1
            by_phase[r.migration_phase.value] = by_phase.get(r.migration_phase.value, 0) + 1
            by_category[r.roi_category.value] = by_category.get(r.roi_category.value, 0) + 1
        high_roi_count = sum(1 for r in self._records if r.roi_pct >= self._roi_threshold)
        rois = [r.roi_pct for r in self._records]
        avg_roi_pct = round(sum(rois) / len(rois), 2) if rois else 0.0
        top_list = self.identify_high_roi_workloads()
        top_roi_workloads = [o["record_id"] for o in top_list[:5]]
        recs: list[str] = []
        if high_roi_count > 0:
            recs.append(f"{high_roi_count} containerization project(s) above ROI target")
        if avg_roi_pct < self._roi_threshold and self._records:
            recs.append(f"Avg ROI {avg_roi_pct}% below target ({self._roi_threshold}%)")
        if not recs:
            recs.append("Containerization ROI is healthy")
        return ContainerizationROIReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_roi_count=high_roi_count,
            avg_roi_pct=avg_roi_pct,
            by_workload_type=by_workload,
            by_migration_phase=by_phase,
            by_roi_category=by_category,
            top_roi_workloads=top_roi_workloads,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("containerization_roi_calculator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        wl_dist: dict[str, int] = {}
        for r in self._records:
            key = r.workload_type.value
            wl_dist[key] = wl_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "roi_threshold": self._roi_threshold,
            "workload_type_distribution": wl_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
