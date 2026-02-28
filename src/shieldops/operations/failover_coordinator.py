"""Failover Coordinator — coordinate cross-region failover operations."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FailoverType(StrEnum):
    DNS_SWITCHOVER = "dns_switchover"
    TRAFFIC_DRAIN = "traffic_drain"
    DATA_REPLICATION = "data_replication"
    COLD_STANDBY = "cold_standby"
    ACTIVE_ACTIVE = "active_active"


class FailoverStatus(StrEnum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class FailoverRegion(StrEnum):
    US_EAST = "us_east"
    US_WEST = "us_west"
    EU_WEST = "eu_west"
    AP_SOUTHEAST = "ap_southeast"
    AP_NORTHEAST = "ap_northeast"


# --- Models ---


class FailoverRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    failover_type: FailoverType = FailoverType.DNS_SWITCHOVER
    status: FailoverStatus = FailoverStatus.INITIATED
    region: FailoverRegion = FailoverRegion.US_EAST
    duration_seconds: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class FailoverPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_name: str = ""
    failover_type: FailoverType = FailoverType.DNS_SWITCHOVER
    region: FailoverRegion = FailoverRegion.US_EAST
    rto_seconds: int = 300
    rpo_seconds: float = 60.0
    created_at: float = Field(default_factory=time.time)


class FailoverCoordinatorReport(BaseModel):
    total_failovers: int = 0
    total_plans: int = 0
    success_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    failed_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MultiRegionFailoverCoordinator:
    """Coordinate cross-region failover operations."""

    def __init__(
        self,
        max_records: int = 200000,
        max_rto_seconds: float = 300.0,
    ) -> None:
        self._max_records = max_records
        self._max_rto_seconds = max_rto_seconds
        self._records: list[FailoverRecord] = []
        self._plans: list[FailoverPlan] = []
        logger.info(
            "failover_coordinator.initialized",
            max_records=max_records,
            max_rto_seconds=max_rto_seconds,
        )

    # -- record / get / list -----------------------------------------

    def record_failover(
        self,
        service_name: str,
        failover_type: FailoverType = (FailoverType.DNS_SWITCHOVER),
        status: FailoverStatus = (FailoverStatus.INITIATED),
        region: FailoverRegion = (FailoverRegion.US_EAST),
        duration_seconds: float = 0.0,
        details: str = "",
    ) -> FailoverRecord:
        record = FailoverRecord(
            service_name=service_name,
            failover_type=failover_type,
            status=status,
            region=region,
            duration_seconds=duration_seconds,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "failover_coordinator.failover_recorded",
            record_id=record.id,
            service_name=service_name,
            failover_type=failover_type.value,
            status=status.value,
        )
        return record

    def get_failover(self, record_id: str) -> FailoverRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_failovers(
        self,
        service_name: str | None = None,
        failover_type: FailoverType | None = None,
        limit: int = 50,
    ) -> list[FailoverRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if failover_type is not None:
            results = [r for r in results if r.failover_type == failover_type]
        return results[-limit:]

    def add_plan(
        self,
        plan_name: str,
        failover_type: FailoverType = (FailoverType.DNS_SWITCHOVER),
        region: FailoverRegion = (FailoverRegion.US_EAST),
        rto_seconds: int = 300,
        rpo_seconds: float = 60.0,
    ) -> FailoverPlan:
        plan = FailoverPlan(
            plan_name=plan_name,
            failover_type=failover_type,
            region=region,
            rto_seconds=rto_seconds,
            rpo_seconds=rpo_seconds,
        )
        self._plans.append(plan)
        if len(self._plans) > self._max_records:
            self._plans = self._plans[-self._max_records :]
        logger.info(
            "failover_coordinator.plan_added",
            plan_name=plan_name,
            failover_type=failover_type.value,
            region=region.value,
        )
        return plan

    # -- domain operations -------------------------------------------

    def analyze_failover_readiness(self, service_name: str) -> dict[str, Any]:
        """Analyze failover readiness for a service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {
                "service_name": service_name,
                "status": "no_data",
            }
        completed = sum(1 for r in records if r.status == FailoverStatus.COMPLETED)
        success_rate = round(completed / len(records) * 100, 2)
        avg_dur = round(
            sum(r.duration_seconds for r in records) / len(records),
            2,
        )
        return {
            "service_name": service_name,
            "failover_count": len(records),
            "completed_count": completed,
            "success_rate": success_rate,
            "avg_duration": avg_dur,
            "meets_threshold": (avg_dur <= self._max_rto_seconds),
        }

    def identify_failed_failovers(
        self,
    ) -> list[dict[str, Any]]:
        """Find services with repeated failures."""
        fail_counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (
                FailoverStatus.FAILED,
                FailoverStatus.ROLLED_BACK,
            ):
                fail_counts[r.service_name] = fail_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in fail_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "failure_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["failure_count"],
            reverse=True,
        )
        return results

    def rank_by_failover_speed(
        self,
    ) -> list[dict[str, Any]]:
        """Rank services by avg duration ascending."""
        totals: dict[str, list[float]] = {}
        for r in self._records:
            totals.setdefault(r.service_name, []).append(r.duration_seconds)
        results: list[dict[str, Any]] = []
        for svc, durs in totals.items():
            avg = round(sum(durs) / len(durs), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_duration": avg,
                    "failover_count": len(durs),
                }
            )
        results.sort(
            key=lambda x: x["avg_duration"],
        )
        return results

    def detect_failover_risks(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with >3 non-COMPLETED."""
        svc_non: dict[str, int] = {}
        for r in self._records:
            if r.status != FailoverStatus.COMPLETED:
                svc_non[r.service_name] = svc_non.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_non.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "non_completed_count": count,
                        "risk_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_completed_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(
        self,
    ) -> FailoverCoordinatorReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.failover_type.value] = by_type.get(r.failover_type.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        completed = sum(1 for r in self._records if r.status == FailoverStatus.COMPLETED)
        rate = (
            round(
                completed / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        failed_count = sum(1 for d in self.identify_failed_failovers())
        recs: list[str] = []
        if rate < 100.0:
            recs.append(f"Success rate {rate}% is below 100.0% threshold")
        if failed_count > 0:
            recs.append(f"{failed_count} service(s) with failed failovers")
        risks = len(self.detect_failover_risks())
        if risks > 0:
            recs.append(f"{risks} service(s) with failover risks")
        if not recs:
            recs.append("Failover readiness meets targets")
        return FailoverCoordinatorReport(
            total_failovers=len(self._records),
            total_plans=len(self._plans),
            success_rate_pct=rate,
            by_type=by_type,
            by_status=by_status,
            failed_count=failed_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._plans.clear()
        logger.info("failover_coordinator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.failover_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_failovers": len(self._records),
            "total_plans": len(self._plans),
            "max_rto_seconds": (self._max_rto_seconds),
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
