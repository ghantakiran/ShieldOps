"""Resource Rightsizing Intelligence
profile workload utilization, recommend instance
family, validate rightsizing safety."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WorkloadProfile(StrEnum):
    STEADY = "steady"
    BURSTY = "bursty"
    BATCH = "batch"
    IDLE_HEAVY = "idle_heavy"


class SizingAction(StrEnum):
    DOWNSIZE = "downsize"
    UPSIZE = "upsize"
    CHANGE_FAMILY = "change_family"
    MAINTAIN = "maintain"


class SafetyLevel(StrEnum):
    SAFE = "safe"
    CAUTION = "caution"
    RISKY = "risky"
    BLOCKED = "blocked"


# --- Models ---


class RightsizingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    workload_profile: WorkloadProfile = WorkloadProfile.STEADY
    sizing_action: SizingAction = SizingAction.MAINTAIN
    safety_level: SafetyLevel = SafetyLevel.SAFE
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    monthly_cost: float = 0.0
    instance_type: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RightsizingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    workload_profile: WorkloadProfile = WorkloadProfile.STEADY
    recommended_action: SizingAction = SizingAction.MAINTAIN
    safety_level: SafetyLevel = SafetyLevel.SAFE
    estimated_savings: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RightsizingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_savings_potential: float = 0.0
    by_workload_profile: dict[str, int] = Field(default_factory=dict)
    by_sizing_action: dict[str, int] = Field(default_factory=dict)
    by_safety_level: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResourceRightsizingIntelligence:
    """Profile workload utilization, recommend
    instance family, validate safety."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RightsizingRecord] = []
        self._analyses: dict[str, RightsizingAnalysis] = {}
        logger.info(
            "resource_rightsizing.init",
            max_records=max_records,
        )

    def record_item(
        self,
        resource_id: str = "",
        workload_profile: WorkloadProfile = (WorkloadProfile.STEADY),
        sizing_action: SizingAction = (SizingAction.MAINTAIN),
        safety_level: SafetyLevel = SafetyLevel.SAFE,
        cpu_utilization: float = 0.0,
        memory_utilization: float = 0.0,
        monthly_cost: float = 0.0,
        instance_type: str = "",
        description: str = "",
    ) -> RightsizingRecord:
        record = RightsizingRecord(
            resource_id=resource_id,
            workload_profile=workload_profile,
            sizing_action=sizing_action,
            safety_level=safety_level,
            cpu_utilization=cpu_utilization,
            memory_utilization=memory_utilization,
            monthly_cost=monthly_cost,
            instance_type=instance_type,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "resource_rightsizing.record_added",
            record_id=record.id,
            resource_id=resource_id,
        )
        return record

    def process(self, key: str) -> RightsizingAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        savings = 0.0
        if rec.sizing_action == SizingAction.DOWNSIZE:
            savings = round(rec.monthly_cost * 0.3, 2)
        elif rec.sizing_action == SizingAction.CHANGE_FAMILY:
            savings = round(rec.monthly_cost * 0.2, 2)
        analysis = RightsizingAnalysis(
            resource_id=rec.resource_id,
            workload_profile=rec.workload_profile,
            recommended_action=rec.sizing_action,
            safety_level=rec.safety_level,
            estimated_savings=savings,
            description=(f"Resource {rec.resource_id} cpu {rec.cpu_utilization}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RightsizingReport:
        by_wp: dict[str, int] = {}
        by_sa: dict[str, int] = {}
        by_sl: dict[str, int] = {}
        total_sav = 0.0
        for r in self._records:
            k = r.workload_profile.value
            by_wp[k] = by_wp.get(k, 0) + 1
            k2 = r.sizing_action.value
            by_sa[k2] = by_sa.get(k2, 0) + 1
            k3 = r.safety_level.value
            by_sl[k3] = by_sl.get(k3, 0) + 1
            if r.sizing_action == SizingAction.DOWNSIZE:
                total_sav += r.monthly_cost * 0.3
        recs: list[str] = []
        downsizable = [r for r in self._records if r.sizing_action == SizingAction.DOWNSIZE]
        if downsizable:
            recs.append(f"{len(downsizable)} resources can be downsized")
        if not recs:
            recs.append("Resources properly sized")
        return RightsizingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_savings_potential=round(total_sav, 2),
            by_workload_profile=by_wp,
            by_sizing_action=by_sa,
            by_safety_level=by_sl,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        wp_dist: dict[str, int] = {}
        for r in self._records:
            k = r.workload_profile.value
            wp_dist[k] = wp_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "workload_profile_dist": wp_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("resource_rightsizing.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def profile_workload_utilization(
        self,
    ) -> list[dict[str, Any]]:
        """Profile utilization per resource."""
        res_cpu: dict[str, list[float]] = {}
        res_mem: dict[str, list[float]] = {}
        res_prof: dict[str, str] = {}
        for r in self._records:
            res_cpu.setdefault(r.resource_id, []).append(r.cpu_utilization)
            res_mem.setdefault(r.resource_id, []).append(r.memory_utilization)
            res_prof[r.resource_id] = r.workload_profile.value
        results: list[dict[str, Any]] = []
        for rid, cpus in res_cpu.items():
            mems = res_mem[rid]
            results.append(
                {
                    "resource_id": rid,
                    "profile": res_prof[rid],
                    "avg_cpu": round(sum(cpus) / len(cpus), 2),
                    "avg_memory": round(sum(mems) / len(mems), 2),
                }
            )
        results.sort(
            key=lambda x: x["avg_cpu"],
        )
        return results

    def recommend_instance_family(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend instance family changes."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.resource_id not in seen:
                seen.add(r.resource_id)
                rec_family = r.instance_type
                if r.cpu_utilization < 20:
                    rec_family = "t3.small"
                elif r.cpu_utilization > 80:
                    rec_family = "c5.xlarge"
                results.append(
                    {
                        "resource_id": (r.resource_id),
                        "current": (r.instance_type),
                        "recommended": rec_family,
                        "action": (r.sizing_action.value),
                    }
                )
        return results

    def validate_rightsizing_safety(
        self,
    ) -> list[dict[str, Any]]:
        """Validate safety of rightsizing."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.resource_id not in seen:
                seen.add(r.resource_id)
                safe = r.safety_level in (
                    SafetyLevel.SAFE,
                    SafetyLevel.CAUTION,
                )
                results.append(
                    {
                        "resource_id": (r.resource_id),
                        "safety": (r.safety_level.value),
                        "can_proceed": safe,
                        "action": (r.sizing_action.value),
                    }
                )
        return results
