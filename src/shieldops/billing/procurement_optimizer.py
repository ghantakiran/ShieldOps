"""Procurement Optimizer — optimize procurement, identify waste, and track savings."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ProcurementType(StrEnum):
    RESERVED_CAPACITY = "reserved_capacity"
    ON_DEMAND = "on_demand"
    SPOT = "spot"
    MARKETPLACE = "marketplace"
    ENTERPRISE = "enterprise"


class ProcurementStatus(StrEnum):
    OPTIMAL = "optimal"
    SUBOPTIMAL = "suboptimal"
    WASTEFUL = "wasteful"
    EXPIRING = "expiring"
    NEEDS_REVIEW = "needs_review"


class OptimizationAction(StrEnum):
    RIGHTSIZE = "rightsize"
    TERMINATE = "terminate"
    CONVERT_RI = "convert_ri"
    SWITCH_REGION = "switch_region"
    NEGOTIATE = "negotiate"


# --- Models ---


class ProcurementRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_name: str = ""
    procurement_type: ProcurementType = ProcurementType.ON_DEMAND
    procurement_status: ProcurementStatus = ProcurementStatus.NEEDS_REVIEW
    optimization_action: OptimizationAction = OptimizationAction.RIGHTSIZE
    waste_pct: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class OptimizationOpportunity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_name: str = ""
    procurement_type: ProcurementType = ProcurementType.ON_DEMAND
    estimated_savings: float = 0.0
    avg_waste_pct: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ProcurementReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_opportunities: int = 0
    wasteful_procurements: int = 0
    avg_waste_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ProcurementOptimizer:
    """Optimize procurement, identify waste, and track savings opportunities."""

    def __init__(
        self,
        max_records: int = 200000,
        max_waste_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_waste_pct = max_waste_pct
        self._records: list[ProcurementRecord] = []
        self._opportunities: list[OptimizationOpportunity] = []
        logger.info(
            "procurement_optimizer.initialized",
            max_records=max_records,
            max_waste_pct=max_waste_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_procurement(
        self,
        resource_name: str,
        procurement_type: ProcurementType = ProcurementType.ON_DEMAND,
        procurement_status: ProcurementStatus = ProcurementStatus.NEEDS_REVIEW,
        optimization_action: OptimizationAction = OptimizationAction.RIGHTSIZE,
        waste_pct: float = 0.0,
        team: str = "",
    ) -> ProcurementRecord:
        record = ProcurementRecord(
            resource_name=resource_name,
            procurement_type=procurement_type,
            procurement_status=procurement_status,
            optimization_action=optimization_action,
            waste_pct=waste_pct,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "procurement_optimizer.recorded",
            record_id=record.id,
            resource_name=resource_name,
            procurement_type=procurement_type.value,
            procurement_status=procurement_status.value,
        )
        return record

    def get_procurement(self, record_id: str) -> ProcurementRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_procurements(
        self,
        procurement_type: ProcurementType | None = None,
        status: ProcurementStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ProcurementRecord]:
        results = list(self._records)
        if procurement_type is not None:
            results = [r for r in results if r.procurement_type == procurement_type]
        if status is not None:
            results = [r for r in results if r.procurement_status == status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_opportunity(
        self,
        opportunity_name: str,
        procurement_type: ProcurementType = ProcurementType.ON_DEMAND,
        estimated_savings: float = 0.0,
        avg_waste_pct: float = 0.0,
        description: str = "",
    ) -> OptimizationOpportunity:
        opportunity = OptimizationOpportunity(
            opportunity_name=opportunity_name,
            procurement_type=procurement_type,
            estimated_savings=estimated_savings,
            avg_waste_pct=avg_waste_pct,
            description=description,
        )
        self._opportunities.append(opportunity)
        if len(self._opportunities) > self._max_records:
            self._opportunities = self._opportunities[-self._max_records :]
        logger.info(
            "procurement_optimizer.opportunity_added",
            opportunity_name=opportunity_name,
            procurement_type=procurement_type.value,
            estimated_savings=estimated_savings,
        )
        return opportunity

    # -- domain operations --------------------------------------------------

    def analyze_procurement_efficiency(self) -> dict[str, Any]:
        """Group by type; return count and avg waste pct per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.procurement_type.value
            type_data.setdefault(key, []).append(r.waste_pct)
        result: dict[str, Any] = {}
        for ptype, wastes in type_data.items():
            result[ptype] = {
                "count": len(wastes),
                "avg_waste_pct": round(sum(wastes) / len(wastes), 2),
            }
        return result

    def identify_waste(self) -> list[dict[str, Any]]:
        """Return records where status is WASTEFUL or EXPIRING."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.procurement_status in (
                ProcurementStatus.WASTEFUL,
                ProcurementStatus.EXPIRING,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "resource_name": r.resource_name,
                        "procurement_status": r.procurement_status.value,
                        "waste_pct": r.waste_pct,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_savings_potential(self) -> list[dict[str, Any]]:
        """Group by team, avg waste pct, sort descending."""
        team_wastes: dict[str, list[float]] = {}
        for r in self._records:
            team_wastes.setdefault(r.team, []).append(r.waste_pct)
        results: list[dict[str, Any]] = []
        for team, wastes in team_wastes.items():
            results.append(
                {
                    "team": team,
                    "avg_waste_pct": round(sum(wastes) / len(wastes), 2),
                    "count": len(wastes),
                }
            )
        results.sort(key=lambda x: x["avg_waste_pct"], reverse=True)
        return results

    def detect_procurement_trends(self) -> dict[str, Any]:
        """Split-half on avg_waste_pct; delta threshold 5.0."""
        if len(self._opportunities) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [o.avg_waste_pct for o in self._opportunities]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ProcurementReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_type[r.procurement_type.value] = by_type.get(r.procurement_type.value, 0) + 1
            by_status[r.procurement_status.value] = by_status.get(r.procurement_status.value, 0) + 1
            by_action[r.optimization_action.value] = (
                by_action.get(r.optimization_action.value, 0) + 1
            )
        wasteful_count = sum(
            1
            for r in self._records
            if r.procurement_status in (ProcurementStatus.WASTEFUL, ProcurementStatus.EXPIRING)
        )
        avg_waste = (
            round(sum(r.waste_pct for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_savings_potential()
        top_items = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if avg_waste > self._max_waste_pct:
            recs.append(f"Avg waste {avg_waste}% exceeds threshold ({self._max_waste_pct}%)")
        if wasteful_count > 0:
            recs.append(f"{wasteful_count} wasteful procurement(s) detected — review resources")
        if not recs:
            recs.append("Procurement efficiency is within acceptable limits")
        return ProcurementReport(
            total_records=len(self._records),
            total_opportunities=len(self._opportunities),
            wasteful_procurements=wasteful_count,
            avg_waste_pct=avg_waste,
            by_type=by_type,
            by_status=by_status,
            by_action=by_action,
            top_items=top_items,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._opportunities.clear()
        logger.info("procurement_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.procurement_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_opportunities": len(self._opportunities),
            "max_waste_pct": self._max_waste_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_resources": len({r.resource_name for r in self._records}),
        }
