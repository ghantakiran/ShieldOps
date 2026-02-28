"""Capacity Burst Manager — handle sudden capacity spikes and burst scaling."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BurstType(StrEnum):
    TRAFFIC_SPIKE = "traffic_spike"
    SEASONAL_PEAK = "seasonal_peak"
    EVENT_DRIVEN = "event_driven"
    FAILURE_RECOVERY = "failure_recovery"
    SCHEDULED_BATCH = "scheduled_batch"


class BurstAction(StrEnum):
    AUTO_SCALE = "auto_scale"
    PRE_PROVISION = "pre_provision"
    QUEUE_TRAFFIC = "queue_traffic"
    SHED_LOAD = "shed_load"
    FAILOVER = "failover"


class BurstStatus(StrEnum):
    DETECTED = "detected"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    BUDGET_EXCEEDED = "budget_exceeded"


# --- Models ---


class BurstRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    burst_type: BurstType = BurstType.TRAFFIC_SPIKE
    action: BurstAction = BurstAction.AUTO_SCALE
    status: BurstStatus = BurstStatus.DETECTED
    cost_impact: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class BurstPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    burst_type: BurstType = BurstType.TRAFFIC_SPIKE
    action: BurstAction = BurstAction.AUTO_SCALE
    max_scale_factor: int = 3
    budget_limit: float = 1000.0
    created_at: float = Field(default_factory=time.time)


class BurstManagerReport(BaseModel):
    total_bursts: int = 0
    total_policies: int = 0
    resolution_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    budget_exceeded_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityBurstManager:
    """Handle sudden capacity spikes and burst scaling."""

    def __init__(
        self,
        max_records: int = 200000,
        max_burst_budget: float = 10000.0,
    ) -> None:
        self._max_records = max_records
        self._max_burst_budget = max_burst_budget
        self._records: list[BurstRecord] = []
        self._policies: list[BurstPolicy] = []
        logger.info(
            "burst_manager.initialized",
            max_records=max_records,
            max_burst_budget=max_burst_budget,
        )

    # -- record / get / list -----------------------------------------

    def record_burst(
        self,
        service_name: str,
        burst_type: BurstType = BurstType.TRAFFIC_SPIKE,
        action: BurstAction = BurstAction.AUTO_SCALE,
        status: BurstStatus = BurstStatus.DETECTED,
        cost_impact: float = 0.0,
        details: str = "",
    ) -> BurstRecord:
        record = BurstRecord(
            service_name=service_name,
            burst_type=burst_type,
            action=action,
            status=status,
            cost_impact=cost_impact,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "burst_manager.burst_recorded",
            record_id=record.id,
            service_name=service_name,
            burst_type=burst_type.value,
            status=status.value,
        )
        return record

    def get_burst(self, record_id: str) -> BurstRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_bursts(
        self,
        service_name: str | None = None,
        burst_type: BurstType | None = None,
        limit: int = 50,
    ) -> list[BurstRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if burst_type is not None:
            results = [r for r in results if r.burst_type == burst_type]
        return results[-limit:]

    def add_policy(
        self,
        policy_name: str,
        burst_type: BurstType = BurstType.TRAFFIC_SPIKE,
        action: BurstAction = BurstAction.AUTO_SCALE,
        max_scale_factor: int = 3,
        budget_limit: float = 1000.0,
    ) -> BurstPolicy:
        policy = BurstPolicy(
            policy_name=policy_name,
            burst_type=burst_type,
            action=action,
            max_scale_factor=max_scale_factor,
            budget_limit=budget_limit,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "burst_manager.policy_added",
            policy_name=policy_name,
            burst_type=burst_type.value,
            action=action.value,
        )
        return policy

    # -- domain operations -------------------------------------------

    def analyze_burst_patterns(self, service_name: str) -> dict[str, Any]:
        """Analyze burst patterns for a service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {
                "service_name": service_name,
                "status": "no_data",
            }
        resolved = sum(1 for r in records if r.status == BurstStatus.RESOLVED)
        resolution_rate = round(resolved / len(records) * 100, 2)
        avg_cost = round(
            sum(r.cost_impact for r in records) / len(records),
            2,
        )
        return {
            "service_name": service_name,
            "burst_count": len(records),
            "resolved_count": resolved,
            "resolution_rate": resolution_rate,
            "avg_cost": avg_cost,
            "meets_threshold": (avg_cost <= self._max_burst_budget),
        }

    def identify_budget_overruns(
        self,
    ) -> list[dict[str, Any]]:
        """Find services with repeated budget overruns."""
        overrun_counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (
                BurstStatus.BUDGET_EXCEEDED,
                BurstStatus.ESCALATED,
            ):
                overrun_counts[r.service_name] = overrun_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in overrun_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "overrun_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["overrun_count"],
            reverse=True,
        )
        return results

    def rank_by_cost_impact(
        self,
    ) -> list[dict[str, Any]]:
        """Rank services by avg cost_impact descending."""
        totals: dict[str, list[float]] = {}
        for r in self._records:
            totals.setdefault(r.service_name, []).append(r.cost_impact)
        results: list[dict[str, Any]] = []
        for svc, costs in totals.items():
            avg = round(sum(costs) / len(costs), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_cost_impact": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_cost_impact"],
            reverse=True,
        )
        return results

    def detect_recurring_bursts(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with >3 non-RESOLVED bursts."""
        svc_non_resolved: dict[str, int] = {}
        for r in self._records:
            if r.status != BurstStatus.RESOLVED:
                svc_non_resolved[r.service_name] = svc_non_resolved.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_non_resolved.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "non_resolved_count": count,
                        "recurring_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_resolved_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> BurstManagerReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.burst_type.value] = by_type.get(r.burst_type.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        resolved_count = sum(1 for r in self._records if r.status == BurstStatus.RESOLVED)
        resolution_rate = (
            round(
                resolved_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        budget_exceeded = sum(1 for r in self._records if r.status == BurstStatus.BUDGET_EXCEEDED)
        overruns = len(self.identify_budget_overruns())
        recs: list[str] = []
        if resolution_rate < 80.0:
            recs.append(f"Resolution rate {resolution_rate}% is below 80.0% threshold")
        if overruns > 0:
            recs.append(f"{overruns} service(s) with budget overruns")
        recurring = len(self.detect_recurring_bursts())
        if recurring > 0:
            recs.append(f"{recurring} service(s) with recurring bursts")
        if not recs:
            recs.append("Burst management capacity is healthy")
        return BurstManagerReport(
            total_bursts=len(self._records),
            total_policies=len(self._policies),
            resolution_rate_pct=resolution_rate,
            by_type=by_type,
            by_status=by_status,
            budget_exceeded_count=budget_exceeded,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("burst_manager.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.burst_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_bursts": len(self._records),
            "total_policies": len(self._policies),
            "max_burst_budget": self._max_burst_budget,
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
