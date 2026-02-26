"""Scaling Efficiency Tracker — measure scaling event efficiency and waste detection."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ScalingType(StrEnum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    AUTO = "auto"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class ScalingOutcome(StrEnum):
    OPTIMAL = "optimal"
    OVER_PROVISIONED = "over_provisioned"
    UNDER_PROVISIONED = "under_provisioned"
    DELAYED = "delayed"
    FAILED = "failed"


class ScalingTrigger(StrEnum):
    CPU_THRESHOLD = "cpu_threshold"
    MEMORY_THRESHOLD = "memory_threshold"
    REQUEST_RATE = "request_rate"
    SCHEDULE = "schedule"
    MANUAL = "manual"


# --- Models ---


class ScalingEventRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    scaling_type: ScalingType = ScalingType.AUTO
    outcome: ScalingOutcome = ScalingOutcome.OPTIMAL
    trigger: ScalingTrigger = ScalingTrigger.CPU_THRESHOLD
    duration_seconds: float = 0.0
    instances_before: int = 0
    instances_after: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ScalingInefficiency(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    inefficiency_type: ScalingOutcome = ScalingOutcome.OVER_PROVISIONED
    waste_pct: float = 0.0
    estimated_cost_waste: float = 0.0
    recommendation: str = ""
    created_at: float = Field(default_factory=time.time)


class ScalingEfficiencyReport(BaseModel):
    total_events: int = 0
    total_inefficiencies: int = 0
    avg_duration_seconds: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    over_provisioned_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ScalingEfficiencyTracker:
    """Measure scaling event efficiency and detect waste."""

    def __init__(
        self,
        max_records: int = 200000,
        max_duration_seconds: float = 300.0,
    ) -> None:
        self._max_records = max_records
        self._max_duration_seconds = max_duration_seconds
        self._records: list[ScalingEventRecord] = []
        self._inefficiencies: list[ScalingInefficiency] = []
        logger.info(
            "scaling_efficiency.initialized",
            max_records=max_records,
            max_duration_seconds=max_duration_seconds,
        )

    # -- record / get / list ---------------------------------------------

    def record_event(
        self,
        service_name: str,
        scaling_type: ScalingType = ScalingType.AUTO,
        outcome: ScalingOutcome = ScalingOutcome.OPTIMAL,
        trigger: ScalingTrigger = ScalingTrigger.CPU_THRESHOLD,
        duration_seconds: float = 0.0,
        instances_before: int = 0,
        instances_after: int = 0,
        details: str = "",
    ) -> ScalingEventRecord:
        record = ScalingEventRecord(
            service_name=service_name,
            scaling_type=scaling_type,
            outcome=outcome,
            trigger=trigger,
            duration_seconds=duration_seconds,
            instances_before=instances_before,
            instances_after=instances_after,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "scaling_efficiency.event_recorded",
            record_id=record.id,
            service_name=service_name,
            outcome=outcome.value,
        )
        return record

    def get_event(self, record_id: str) -> ScalingEventRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_events(
        self,
        service_name: str | None = None,
        scaling_type: ScalingType | None = None,
        limit: int = 50,
    ) -> list[ScalingEventRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if scaling_type is not None:
            results = [r for r in results if r.scaling_type == scaling_type]
        return results[-limit:]

    def record_inefficiency(
        self,
        service_name: str,
        inefficiency_type: ScalingOutcome = ScalingOutcome.OVER_PROVISIONED,
        waste_pct: float = 0.0,
        estimated_cost_waste: float = 0.0,
        recommendation: str = "",
    ) -> ScalingInefficiency:
        ineff = ScalingInefficiency(
            service_name=service_name,
            inefficiency_type=inefficiency_type,
            waste_pct=waste_pct,
            estimated_cost_waste=estimated_cost_waste,
            recommendation=recommendation,
        )
        self._inefficiencies.append(ineff)
        if len(self._inefficiencies) > self._max_records:
            self._inefficiencies = self._inefficiencies[-self._max_records :]
        logger.info(
            "scaling_efficiency.inefficiency_recorded",
            service_name=service_name,
            waste_pct=waste_pct,
        )
        return ineff

    # -- domain operations -----------------------------------------------

    def analyze_scaling_efficiency(self, service_name: str) -> dict[str, Any]:
        """Analyze scaling efficiency for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        latest = records[-1]
        optimal = sum(1 for r in records if r.outcome == ScalingOutcome.OPTIMAL)
        rate = round(optimal / len(records) * 100, 2)
        return {
            "service_name": service_name,
            "total_events": len(records),
            "optimal_rate_pct": rate,
            "last_outcome": latest.outcome.value,
            "last_type": latest.scaling_type.value,
        }

    def identify_over_provisioned(self) -> list[dict[str, Any]]:
        """Find over-provisioned scaling events."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.outcome == ScalingOutcome.OVER_PROVISIONED:
                results.append(
                    {
                        "service_name": r.service_name,
                        "scaling_type": r.scaling_type.value,
                        "instances_before": r.instances_before,
                        "instances_after": r.instances_after,
                        "excess": r.instances_after - r.instances_before,
                    }
                )
        results.sort(key=lambda x: x["excess"], reverse=True)
        return results

    def rank_by_waste(self) -> list[dict[str, Any]]:
        """Rank inefficiencies by waste percentage."""
        results: list[dict[str, Any]] = []
        for i in self._inefficiencies:
            results.append(
                {
                    "service_name": i.service_name,
                    "waste_pct": i.waste_pct,
                    "estimated_cost_waste": i.estimated_cost_waste,
                    "inefficiency_type": i.inefficiency_type.value,
                }
            )
        results.sort(key=lambda x: x["waste_pct"], reverse=True)
        return results

    def detect_scaling_delays(self) -> list[dict[str, Any]]:
        """Detect scaling events that exceeded max duration."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.duration_seconds > self._max_duration_seconds:
                results.append(
                    {
                        "service_name": r.service_name,
                        "duration_seconds": r.duration_seconds,
                        "max_allowed": self._max_duration_seconds,
                        "excess_seconds": round(
                            r.duration_seconds - self._max_duration_seconds,
                            2,
                        ),
                    }
                )
        results.sort(key=lambda x: x["duration_seconds"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ScalingEfficiencyReport:
        by_type: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_type[r.scaling_type.value] = by_type.get(r.scaling_type.value, 0) + 1
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
        avg_dur = (
            round(
                sum(r.duration_seconds for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        over_prov = sum(1 for r in self._records if r.outcome == ScalingOutcome.OVER_PROVISIONED)
        recs: list[str] = []
        if over_prov > 0:
            recs.append(f"{over_prov} over-provisioned scaling event(s)")
        delayed = sum(1 for r in self._records if r.duration_seconds > self._max_duration_seconds)
        if delayed > 0:
            recs.append(f"{delayed} scaling event(s) exceeded max duration")
        if not recs:
            recs.append("Scaling efficiency meets targets")
        return ScalingEfficiencyReport(
            total_events=len(self._records),
            total_inefficiencies=len(self._inefficiencies),
            avg_duration_seconds=avg_dur,
            by_type=by_type,
            by_outcome=by_outcome,
            over_provisioned_count=over_prov,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._inefficiencies.clear()
        logger.info("scaling_efficiency.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.scaling_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_events": len(self._records),
            "total_inefficiencies": len(self._inefficiencies),
            "max_duration_seconds": self._max_duration_seconds,
            "type_distribution": type_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
