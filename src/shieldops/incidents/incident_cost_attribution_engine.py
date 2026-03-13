"""Incident Cost Attribution Engine — compute cost breakdown,
detect high-cost patterns, rank incidents by total cost."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CostCategory(StrEnum):
    ENGINEERING_TIME = "engineering_time"
    REVENUE_LOSS = "revenue_loss"
    SLA_PENALTY = "sla_penalty"
    INFRASTRUCTURE = "infrastructure"


class CostPeriod(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class CostSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class IncidentCostRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    cost_category: CostCategory = CostCategory.ENGINEERING_TIME
    cost_period: CostPeriod = CostPeriod.DAILY
    cost_severity: CostSeverity = CostSeverity.MEDIUM
    cost_amount: float = 0.0
    currency: str = "USD"
    service: str = ""
    team: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentCostAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    total_cost: float = 0.0
    primary_category: CostCategory = CostCategory.ENGINEERING_TIME
    is_high_cost: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentCostReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_cost: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_period: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentCostAttributionEngine:
    """Compute incident cost breakdown, detect high-cost patterns,
    rank incidents by total cost."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[IncidentCostRecord] = []
        self._analyses: dict[str, IncidentCostAnalysis] = {}
        logger.info(
            "incident_cost_attribution_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        incident_id: str = "",
        cost_category: CostCategory = CostCategory.ENGINEERING_TIME,
        cost_period: CostPeriod = CostPeriod.DAILY,
        cost_severity: CostSeverity = CostSeverity.MEDIUM,
        cost_amount: float = 0.0,
        currency: str = "USD",
        service: str = "",
        team: str = "",
        description: str = "",
    ) -> IncidentCostRecord:
        record = IncidentCostRecord(
            incident_id=incident_id,
            cost_category=cost_category,
            cost_period=cost_period,
            cost_severity=cost_severity,
            cost_amount=cost_amount,
            currency=currency,
            service=service,
            team=team,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_cost_attribution.record_added",
            record_id=record.id,
            incident_id=incident_id,
        )
        return record

    def process(self, key: str) -> IncidentCostAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        related = [r for r in self._records if r.incident_id == rec.incident_id]
        total = round(sum(r.cost_amount for r in related), 2)
        is_high = total > 10000 or rec.cost_severity in (CostSeverity.CRITICAL, CostSeverity.HIGH)
        analysis = IncidentCostAnalysis(
            incident_id=rec.incident_id,
            total_cost=total,
            primary_category=rec.cost_category,
            is_high_cost=is_high,
            description=f"Incident {rec.incident_id} total cost ${total}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> IncidentCostReport:
        by_cat: dict[str, int] = {}
        by_per: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        total_cost = 0.0
        for r in self._records:
            by_cat[r.cost_category.value] = by_cat.get(r.cost_category.value, 0) + 1
            by_per[r.cost_period.value] = by_per.get(r.cost_period.value, 0) + 1
            by_sev[r.cost_severity.value] = by_sev.get(r.cost_severity.value, 0) + 1
            total_cost += r.cost_amount
        recs: list[str] = []
        if total_cost > 100000:
            recs.append(f"Total incident cost ${round(total_cost, 2)} exceeds threshold")
        if not recs:
            recs.append("Incident costs within acceptable range")
        return IncidentCostReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_cost=round(total_cost, 2),
            by_category=by_cat,
            by_period=by_per,
            by_severity=by_sev,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            k = r.cost_category.value
            cat_dist[k] = cat_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "category_distribution": cat_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("incident_cost_attribution_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_incident_cost_breakdown(self) -> list[dict[str, Any]]:
        """Compute cost breakdown per incident."""
        incident_costs: dict[str, dict[str, float]] = {}
        for r in self._records:
            if r.incident_id not in incident_costs:
                incident_costs[r.incident_id] = {}
            cat = r.cost_category.value
            incident_costs[r.incident_id][cat] = (
                incident_costs[r.incident_id].get(cat, 0.0) + r.cost_amount
            )
        results: list[dict[str, Any]] = []
        for iid, breakdown in incident_costs.items():
            total = round(sum(breakdown.values()), 2)
            results.append(
                {
                    "incident_id": iid,
                    "total_cost": total,
                    "breakdown": {k: round(v, 2) for k, v in breakdown.items()},
                }
            )
        results.sort(key=lambda x: x["total_cost"], reverse=True)
        return results

    def detect_high_cost_patterns(self) -> list[dict[str, Any]]:
        """Detect services/teams with high incident costs."""
        service_costs: dict[str, float] = {}
        service_counts: dict[str, int] = {}
        for r in self._records:
            service_costs[r.service] = service_costs.get(r.service, 0.0) + r.cost_amount
            service_counts[r.service] = service_counts.get(r.service, 0) + 1
        avg_cost = sum(service_costs.values()) / len(service_costs) if service_costs else 0.0
        results: list[dict[str, Any]] = []
        for svc, total in service_costs.items():
            if total > avg_cost * 1.5:
                results.append(
                    {
                        "service": svc,
                        "total_cost": round(total, 2),
                        "incident_count": service_counts[svc],
                        "avg_cost_per_incident": round(total / service_counts[svc], 2),
                    }
                )
        results.sort(key=lambda x: x["total_cost"], reverse=True)
        return results

    def rank_incidents_by_total_cost(self) -> list[dict[str, Any]]:
        """Rank incidents by total cost."""
        incident_data: dict[str, float] = {}
        incident_sev: dict[str, str] = {}
        for r in self._records:
            incident_data[r.incident_id] = incident_data.get(r.incident_id, 0.0) + r.cost_amount
            incident_sev[r.incident_id] = r.cost_severity.value
        results: list[dict[str, Any]] = []
        for iid, total in incident_data.items():
            results.append(
                {
                    "incident_id": iid,
                    "severity": incident_sev[iid],
                    "total_cost": round(total, 2),
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["total_cost"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
