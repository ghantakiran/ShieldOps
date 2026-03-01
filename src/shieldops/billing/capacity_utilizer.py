"""Capacity Utilization Optimizer — analyze and optimize resource capacity utilization."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResourceType(StrEnum):
    COMPUTE = "compute"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    GPU = "gpu"


class UtilizationBand(StrEnum):
    OVER_PROVISIONED = "over_provisioned"
    OPTIMAL = "optimal"
    UNDER_UTILIZED = "under_utilized"
    IDLE = "idle"
    UNKNOWN = "unknown"


class OptimizationAction(StrEnum):
    DOWNSIZE = "downsize"
    UPSIZE = "upsize"
    TERMINATE = "terminate"
    RIGHTSIZE = "rightsize"
    SCHEDULE = "schedule"


# --- Models ---


class UtilizationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_type: ResourceType = ResourceType.COMPUTE
    utilization_pct: float = 0.0
    band: UtilizationBand = UtilizationBand.OPTIMAL
    team: str = ""
    recommended_action: OptimizationAction = OptimizationAction.RIGHTSIZE
    potential_savings: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class OptimizationSuggestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    action: OptimizationAction = OptimizationAction.RIGHTSIZE
    current_size: str = ""
    recommended_size: str = ""
    estimated_savings: float = 0.0
    confidence_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CapacityUtilizerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_suggestions: int = 0
    avg_utilization_pct: float = 0.0
    by_resource_type: dict[str, int] = Field(default_factory=dict)
    by_band: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    total_savings_potential: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityUtilizationOptimizer:
    """Analyze resource capacity utilization and recommend optimizations."""

    def __init__(
        self,
        max_records: int = 200000,
        optimal_utilization_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._optimal_utilization_pct = optimal_utilization_pct
        self._records: list[UtilizationRecord] = []
        self._suggestions: list[OptimizationSuggestion] = []
        logger.info(
            "capacity_utilizer.initialized",
            max_records=max_records,
            optimal_utilization_pct=optimal_utilization_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_utilization(
        self,
        resource_id: str,
        resource_type: ResourceType = ResourceType.COMPUTE,
        utilization_pct: float = 0.0,
        band: UtilizationBand = UtilizationBand.OPTIMAL,
        team: str = "",
        recommended_action: OptimizationAction = OptimizationAction.RIGHTSIZE,
        potential_savings: float = 0.0,
        details: str = "",
    ) -> UtilizationRecord:
        record = UtilizationRecord(
            resource_id=resource_id,
            resource_type=resource_type,
            utilization_pct=utilization_pct,
            band=band,
            team=team,
            recommended_action=recommended_action,
            potential_savings=potential_savings,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capacity_utilizer.recorded",
            record_id=record.id,
            resource_id=resource_id,
            resource_type=resource_type.value,
            band=band.value,
        )
        return record

    def get_utilization(self, record_id: str) -> UtilizationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_utilizations(
        self,
        resource_type: ResourceType | None = None,
        band: UtilizationBand | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[UtilizationRecord]:
        results = list(self._records)
        if resource_type is not None:
            results = [r for r in results if r.resource_type == resource_type]
        if band is not None:
            results = [r for r in results if r.band == band]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_suggestion(
        self,
        resource_id: str,
        action: OptimizationAction = OptimizationAction.RIGHTSIZE,
        current_size: str = "",
        recommended_size: str = "",
        estimated_savings: float = 0.0,
        confidence_pct: float = 0.0,
    ) -> OptimizationSuggestion:
        suggestion = OptimizationSuggestion(
            resource_id=resource_id,
            action=action,
            current_size=current_size,
            recommended_size=recommended_size,
            estimated_savings=estimated_savings,
            confidence_pct=confidence_pct,
        )
        self._suggestions.append(suggestion)
        if len(self._suggestions) > self._max_records:
            self._suggestions = self._suggestions[-self._max_records :]
        logger.info(
            "capacity_utilizer.suggestion_added",
            resource_id=resource_id,
            action=action.value,
            estimated_savings=estimated_savings,
        )
        return suggestion

    # -- domain operations -----------------------------------------------

    def analyze_utilization_by_type(self) -> list[dict[str, Any]]:
        """Analyze average utilization per resource type."""
        type_utils: dict[str, list[float]] = {}
        for r in self._records:
            type_utils.setdefault(r.resource_type.value, []).append(r.utilization_pct)
        results: list[dict[str, Any]] = []
        for rtype, utils in type_utils.items():
            results.append(
                {
                    "resource_type": rtype,
                    "avg_utilization_pct": round(sum(utils) / len(utils), 2),
                    "record_count": len(utils),
                }
            )
        results.sort(key=lambda x: x["avg_utilization_pct"], reverse=True)
        return results

    def identify_optimization_opportunities(self) -> list[dict[str, Any]]:
        """Find resources that are under-utilized, over-provisioned, or idle."""
        targets = {
            UtilizationBand.UNDER_UTILIZED,
            UtilizationBand.OVER_PROVISIONED,
            UtilizationBand.IDLE,
        }
        opportunities: list[dict[str, Any]] = []
        for r in self._records:
            if r.band in targets:
                opportunities.append(
                    {
                        "record_id": r.id,
                        "resource_id": r.resource_id,
                        "resource_type": r.resource_type.value,
                        "utilization_pct": r.utilization_pct,
                        "band": r.band.value,
                        "potential_savings": r.potential_savings,
                    }
                )
        opportunities.sort(key=lambda x: x["potential_savings"], reverse=True)
        return opportunities

    def rank_by_savings_potential(self) -> list[dict[str, Any]]:
        """Rank teams by total potential savings."""
        team_savings: dict[str, list[float]] = {}
        for r in self._records:
            team_savings.setdefault(r.team, []).append(r.potential_savings)
        results: list[dict[str, Any]] = []
        for team, savings in team_savings.items():
            results.append(
                {
                    "team": team,
                    "total_savings": round(sum(savings), 2),
                    "avg_savings": round(sum(savings) / len(savings), 2),
                    "record_count": len(savings),
                }
            )
        results.sort(key=lambda x: x["total_savings"], reverse=True)
        return results

    def detect_utilization_trends(self) -> list[dict[str, Any]]:
        """Detect utilization trends using split-half comparison."""
        team_records: dict[str, list[float]] = {}
        for r in self._records:
            team_records.setdefault(r.team, []).append(r.utilization_pct)
        results: list[dict[str, Any]] = []
        for team, utils in team_records.items():
            if len(utils) < 4:
                results.append({"team": team, "trend": "insufficient_data"})
                continue
            mid = len(utils) // 2
            first_half_avg = sum(utils[:mid]) / mid
            second_half_avg = sum(utils[mid:]) / (len(utils) - mid)
            delta = second_half_avg - first_half_avg
            if delta > 5.0:
                trend = "increasing"
            elif delta < -5.0:
                trend = "decreasing"
            else:
                trend = "stable"
            results.append(
                {
                    "team": team,
                    "first_half_avg": round(first_half_avg, 2),
                    "second_half_avg": round(second_half_avg, 2),
                    "delta": round(delta, 2),
                    "trend": trend,
                }
            )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> CapacityUtilizerReport:
        by_resource_type: dict[str, int] = {}
        by_band: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_resource_type[r.resource_type.value] = (
                by_resource_type.get(r.resource_type.value, 0) + 1
            )
            by_band[r.band.value] = by_band.get(r.band.value, 0) + 1
            by_action[r.recommended_action.value] = by_action.get(r.recommended_action.value, 0) + 1
        avg_util = (
            round(
                sum(r.utilization_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        total_savings = round(sum(r.potential_savings for r in self._records), 2)
        opportunities = self.identify_optimization_opportunities()
        recs: list[str] = []
        if avg_util < self._optimal_utilization_pct:
            recs.append(
                f"Average utilization {avg_util}% is below"
                f" {self._optimal_utilization_pct}% optimal target"
            )
        if len(opportunities) > 0:
            recs.append(f"{len(opportunities)} optimization opportunity(ies) found")
        if not recs:
            recs.append("Capacity utilization within optimal parameters")
        return CapacityUtilizerReport(
            total_records=len(self._records),
            total_suggestions=len(self._suggestions),
            avg_utilization_pct=avg_util,
            by_resource_type=by_resource_type,
            by_band=by_band,
            by_action=by_action,
            total_savings_potential=total_savings,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._suggestions.clear()
        logger.info("capacity_utilizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.resource_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_suggestions": len(self._suggestions),
            "optimal_utilization_pct": self._optimal_utilization_pct,
            "resource_type_distribution": type_dist,
            "unique_resources": len({r.resource_id for r in self._records}),
        }
