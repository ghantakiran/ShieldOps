"""SLO-Driven Auto-Scaler — auto-scale resources based on SLO burn rate."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ScaleDirection(StrEnum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"
    NO_ACTION = "no_action"


class ScaleTrigger(StrEnum):
    BURN_RATE = "burn_rate"
    ERROR_BUDGET = "error_budget"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    PREDICTIVE = "predictive"


class ScaleOutcome(StrEnum):
    SUCCESSFUL = "successful"
    PARTIAL = "partial"
    FAILED = "failed"
    COOLDOWN = "cooldown"
    REJECTED = "rejected"


# --- Models ---


class ScaleRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    scale_direction: ScaleDirection = ScaleDirection.SCALE_UP
    scale_trigger: ScaleTrigger = ScaleTrigger.BURN_RATE
    scale_outcome: ScaleOutcome = ScaleOutcome.SUCCESSFUL
    replica_delta: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ScalePolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    scale_direction: ScaleDirection = ScaleDirection.SCALE_OUT
    scale_trigger: ScaleTrigger = ScaleTrigger.ERROR_BUDGET
    cooldown_seconds: float = 300.0
    created_at: float = Field(default_factory=time.time)


class SLOAutoScalerReport(BaseModel):
    total_scales: int = 0
    total_policies: int = 0
    success_rate_pct: float = 0.0
    by_direction: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    failure_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLOAutoScaler:
    """Auto-scale resources based on SLO burn rate."""

    def __init__(
        self,
        max_records: int = 200000,
        max_replica_delta: int = 10,
    ) -> None:
        self._max_records = max_records
        self._max_replica_delta = max_replica_delta
        self._records: list[ScaleRecord] = []
        self._policies: list[ScalePolicy] = []
        logger.info(
            "slo_auto_scaler.initialized",
            max_records=max_records,
            max_replica_delta=max_replica_delta,
        )

    # -- record / get / list ---------------------------------------------

    def record_scale(
        self,
        service_name: str,
        scale_direction: ScaleDirection = ScaleDirection.SCALE_UP,
        scale_trigger: ScaleTrigger = ScaleTrigger.BURN_RATE,
        scale_outcome: ScaleOutcome = ScaleOutcome.SUCCESSFUL,
        replica_delta: int = 0,
        details: str = "",
    ) -> ScaleRecord:
        record = ScaleRecord(
            service_name=service_name,
            scale_direction=scale_direction,
            scale_trigger=scale_trigger,
            scale_outcome=scale_outcome,
            replica_delta=replica_delta,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "slo_auto_scaler.scale_recorded",
            record_id=record.id,
            service_name=service_name,
            scale_outcome=scale_outcome.value,
        )
        return record

    def get_scale(self, record_id: str) -> ScaleRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_scales(
        self,
        service_name: str | None = None,
        scale_direction: ScaleDirection | None = None,
        limit: int = 50,
    ) -> list[ScaleRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if scale_direction is not None:
            results = [r for r in results if r.scale_direction == scale_direction]
        return results[-limit:]

    def add_policy(
        self,
        policy_name: str,
        scale_direction: ScaleDirection = ScaleDirection.SCALE_OUT,
        scale_trigger: ScaleTrigger = ScaleTrigger.ERROR_BUDGET,
        cooldown_seconds: float = 300.0,
    ) -> ScalePolicy:
        policy = ScalePolicy(
            policy_name=policy_name,
            scale_direction=scale_direction,
            scale_trigger=scale_trigger,
            cooldown_seconds=cooldown_seconds,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "slo_auto_scaler.policy_added",
            policy_name=policy_name,
            scale_direction=scale_direction.value,
        )
        return policy

    # -- domain operations -----------------------------------------------

    def analyze_scaling_efficiency(self, service_name: str) -> dict[str, Any]:
        """Analyze success rate for a service's scaling operations."""
        svc_records = [r for r in self._records if r.service_name == service_name]
        if not svc_records:
            return {"service_name": service_name, "status": "no_data"}
        success_count = sum(1 for r in svc_records if r.scale_outcome == ScaleOutcome.SUCCESSFUL)
        success_rate = round((success_count / len(svc_records)) * 100, 2)
        avg_delta = round(sum(r.replica_delta for r in svc_records) / len(svc_records), 2)
        return {
            "service_name": service_name,
            "success_rate": success_rate,
            "record_count": len(svc_records),
            "avg_replica_delta": avg_delta,
            "max_replica_delta": self._max_replica_delta,
        }

    def identify_scaling_failures(self) -> list[dict[str, Any]]:
        """Find services with more than one FAILED or REJECTED scale."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.scale_outcome in (ScaleOutcome.FAILED, ScaleOutcome.REJECTED):
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 1:
                results.append({"service_name": svc, "failure_count": count})
        results.sort(key=lambda x: x["failure_count"], reverse=True)
        return results

    def rank_by_scale_frequency(self) -> list[dict[str, Any]]:
        """Rank services by average replica delta descending."""
        svc_deltas: dict[str, list[int]] = {}
        for r in self._records:
            svc_deltas.setdefault(r.service_name, []).append(r.replica_delta)
        results: list[dict[str, Any]] = []
        for svc, deltas in svc_deltas.items():
            avg = round(sum(deltas) / len(deltas), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_replica_delta": avg,
                    "record_count": len(deltas),
                }
            )
        results.sort(key=lambda x: x["avg_replica_delta"], reverse=True)
        return results

    def detect_scaling_oscillations(self) -> list[dict[str, Any]]:
        """Detect services with more than 3 scaling records."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append({"service_name": svc, "record_count": count})
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> SLOAutoScalerReport:
        by_direction: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_direction[r.scale_direction.value] = by_direction.get(r.scale_direction.value, 0) + 1
            by_outcome[r.scale_outcome.value] = by_outcome.get(r.scale_outcome.value, 0) + 1
        success_count = sum(1 for r in self._records if r.scale_outcome == ScaleOutcome.SUCCESSFUL)
        success_rate = (
            round((success_count / len(self._records)) * 100, 2) if self._records else 0.0
        )
        failure_count = sum(1 for r in self._records if r.scale_outcome == ScaleOutcome.FAILED)
        recs: list[str] = []
        if failure_count > 0:
            recs.append(f"{failure_count} scaling action(s) failed")
        rejected_count = sum(1 for r in self._records if r.scale_outcome == ScaleOutcome.REJECTED)
        if rejected_count > 0:
            recs.append(f"{rejected_count} scaling action(s) rejected")
        if not recs:
            recs.append("SLO auto-scaling is healthy")
        return SLOAutoScalerReport(
            total_scales=len(self._records),
            total_policies=len(self._policies),
            success_rate_pct=success_rate,
            by_direction=by_direction,
            by_outcome=by_outcome,
            failure_count=failure_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("slo_auto_scaler.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        direction_dist: dict[str, int] = {}
        for r in self._records:
            key = r.scale_direction.value
            direction_dist[key] = direction_dist.get(key, 0) + 1
        return {
            "total_scales": len(self._records),
            "total_policies": len(self._policies),
            "max_replica_delta": self._max_replica_delta,
            "direction_distribution": direction_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
