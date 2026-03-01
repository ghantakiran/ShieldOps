"""Capacity Scaling Advisor — advise on scaling decisions and efficiency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ScalingAction(StrEnum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"
    NO_ACTION = "no_action"


class ProvisioningStatus(StrEnum):
    OVER_PROVISIONED = "over_provisioned"
    RIGHT_SIZED = "right_sized"
    UNDER_PROVISIONED = "under_provisioned"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ScalingTrigger(StrEnum):
    CPU_THRESHOLD = "cpu_threshold"
    MEMORY_THRESHOLD = "memory_threshold"
    REQUEST_RATE = "request_rate"
    SCHEDULE = "schedule"
    MANUAL = "manual"


# --- Models ---


class ScalingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scaling_id: str = ""
    scaling_action: ScalingAction = ScalingAction.NO_ACTION
    provisioning_status: ProvisioningStatus = ProvisioningStatus.UNKNOWN
    scaling_trigger: ScalingTrigger = ScalingTrigger.MANUAL
    efficiency_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ScalingRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scaling_id: str = ""
    scaling_action: ScalingAction = ScalingAction.NO_ACTION
    recommendation_score: float = 0.0
    threshold: float = 70.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacityScalingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_recommendations: int = 0
    inefficient_count: int = 0
    avg_efficiency_score: float = 0.0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_trigger: dict[str, int] = Field(default_factory=dict)
    top_inefficient: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityScalingAdvisor:
    """Advise on scaling decisions, analyze scaling efficiency."""

    def __init__(
        self,
        max_records: int = 200000,
        min_efficiency_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_efficiency_score = min_efficiency_score
        self._records: list[ScalingRecord] = []
        self._recommendations: list[ScalingRecommendation] = []
        logger.info(
            "capacity_scaling_advisor.initialized",
            max_records=max_records,
            min_efficiency_score=min_efficiency_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_scaling(
        self,
        scaling_id: str,
        scaling_action: ScalingAction = ScalingAction.NO_ACTION,
        provisioning_status: ProvisioningStatus = ProvisioningStatus.UNKNOWN,
        scaling_trigger: ScalingTrigger = ScalingTrigger.MANUAL,
        efficiency_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ScalingRecord:
        record = ScalingRecord(
            scaling_id=scaling_id,
            scaling_action=scaling_action,
            provisioning_status=provisioning_status,
            scaling_trigger=scaling_trigger,
            efficiency_score=efficiency_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capacity_scaling_advisor.scaling_recorded",
            record_id=record.id,
            scaling_id=scaling_id,
            scaling_action=scaling_action.value,
            provisioning_status=provisioning_status.value,
        )
        return record

    def get_scaling(self, record_id: str) -> ScalingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_scalings(
        self,
        scaling_action: ScalingAction | None = None,
        provisioning_status: ProvisioningStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ScalingRecord]:
        results = list(self._records)
        if scaling_action is not None:
            results = [r for r in results if r.scaling_action == scaling_action]
        if provisioning_status is not None:
            results = [r for r in results if r.provisioning_status == provisioning_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_recommendation(
        self,
        scaling_id: str,
        scaling_action: ScalingAction = ScalingAction.NO_ACTION,
        recommendation_score: float = 0.0,
        threshold: float = 70.0,
        description: str = "",
    ) -> ScalingRecommendation:
        breached = recommendation_score < threshold
        recommendation = ScalingRecommendation(
            scaling_id=scaling_id,
            scaling_action=scaling_action,
            recommendation_score=recommendation_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._recommendations.append(recommendation)
        if len(self._recommendations) > self._max_records:
            self._recommendations = self._recommendations[-self._max_records :]
        logger.info(
            "capacity_scaling_advisor.recommendation_added",
            scaling_id=scaling_id,
            scaling_action=scaling_action.value,
            recommendation_score=recommendation_score,
            breached=breached,
        )
        return recommendation

    # -- domain operations --------------------------------------------------

    def analyze_scaling_distribution(self) -> dict[str, Any]:
        """Group by scaling_action; return count and avg efficiency."""
        action_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.scaling_action.value
            action_data.setdefault(key, []).append(r.efficiency_score)
        result: dict[str, Any] = {}
        for action, scores in action_data.items():
            result[action] = {
                "count": len(scores),
                "avg_efficiency_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_inefficient_scaling(self) -> list[dict[str, Any]]:
        """Return scalings where status is OVER or UNDER provisioned."""
        inefficient_statuses = {
            ProvisioningStatus.OVER_PROVISIONED,
            ProvisioningStatus.UNDER_PROVISIONED,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.provisioning_status in inefficient_statuses:
                results.append(
                    {
                        "record_id": r.id,
                        "scaling_id": r.scaling_id,
                        "scaling_action": r.scaling_action.value,
                        "provisioning_status": (r.provisioning_status.value),
                        "efficiency_score": r.efficiency_score,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["efficiency_score"], reverse=False)
        return results

    def rank_by_efficiency(self) -> list[dict[str, Any]]:
        """Group by service, avg efficiency_score, sort asc — worst."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            service_scores.setdefault(r.service, []).append(r.efficiency_score)
        results: list[dict[str, Any]] = []
        for svc, scores in service_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_efficiency_score": round(sum(scores) / len(scores), 2),
                    "scaling_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_efficiency_score"], reverse=False)
        return results

    def detect_scaling_trends(self) -> dict[str, Any]:
        """Split-half on recommendation_score; delta threshold 5.0."""
        if len(self._recommendations) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [r.recommendation_score for r in self._recommendations]
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

    def generate_report(self) -> CapacityScalingReport:
        by_action: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_trigger: dict[str, int] = {}
        for r in self._records:
            by_action[r.scaling_action.value] = by_action.get(r.scaling_action.value, 0) + 1
            by_status[r.provisioning_status.value] = (
                by_status.get(r.provisioning_status.value, 0) + 1
            )
            by_trigger[r.scaling_trigger.value] = by_trigger.get(r.scaling_trigger.value, 0) + 1
        inefficient_count = sum(
            1
            for r in self._records
            if r.provisioning_status
            in {
                ProvisioningStatus.OVER_PROVISIONED,
                ProvisioningStatus.UNDER_PROVISIONED,
            }
        )
        avg_efficiency = (
            round(
                sum(r.efficiency_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        inefficient_list = self.identify_inefficient_scaling()
        top_inefficient = [i["scaling_id"] for i in inefficient_list]
        recs: list[str] = []
        if inefficient_count > 0:
            recs.append(
                f"{inefficient_count} inefficient scaling(s) detected — review provisioning"
            )
        low_eff = sum(1 for r in self._records if r.efficiency_score < self._min_efficiency_score)
        if low_eff > 0:
            recs.append(
                f"{low_eff} scaling(s) below efficiency threshold ({self._min_efficiency_score}%)"
            )
        if not recs:
            recs.append("Scaling efficiency levels are acceptable")
        return CapacityScalingReport(
            total_records=len(self._records),
            total_recommendations=len(self._recommendations),
            inefficient_count=inefficient_count,
            avg_efficiency_score=avg_efficiency,
            by_action=by_action,
            by_status=by_status,
            by_trigger=by_trigger,
            top_inefficient=top_inefficient,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._recommendations.clear()
        logger.info("capacity_scaling_advisor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        action_dist: dict[str, int] = {}
        for r in self._records:
            key = r.scaling_action.value
            action_dist[key] = action_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_recommendations": len(self._recommendations),
            "min_efficiency_score": self._min_efficiency_score,
            "action_distribution": action_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
