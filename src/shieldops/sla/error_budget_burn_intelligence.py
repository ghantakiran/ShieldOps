"""Error Budget Burn Intelligence
compute burn rate trajectory, detect accelerated burn,
rank services by budget remaining."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class BurnRate(StrEnum):
    FAST = "fast"
    MODERATE = "moderate"
    SLOW = "slow"
    NONE = "none"


class BudgetStatus(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


class BurnCause(StrEnum):
    DEPLOYMENT = "deployment"
    INCIDENT = "incident"
    DEGRADATION = "degradation"
    TRAFFIC = "traffic"


# --- Models ---


class ErrorBudgetBurnRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    burn_rate: BurnRate = BurnRate.SLOW
    budget_status: BudgetStatus = BudgetStatus.HEALTHY
    burn_cause: BurnCause = BurnCause.INCIDENT
    budget_total: float = 100.0
    budget_consumed: float = 0.0
    burn_velocity: float = 0.0
    window_hours: int = 24
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ErrorBudgetBurnAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    remaining_pct: float = 0.0
    burn_rate: BurnRate = BurnRate.SLOW
    accelerated: bool = False
    data_points: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ErrorBudgetBurnReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_budget_remaining: float = 0.0
    by_burn_rate: dict[str, int] = Field(default_factory=dict)
    by_budget_status: dict[str, int] = Field(default_factory=dict)
    by_burn_cause: dict[str, int] = Field(default_factory=dict)
    exhausted_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ErrorBudgetBurnIntelligence:
    """Compute burn rate trajectory, detect accelerated
    burn, rank services by budget remaining."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ErrorBudgetBurnRecord] = []
        self._analyses: dict[str, ErrorBudgetBurnAnalysis] = {}
        logger.info(
            "error_budget_burn_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        service_id: str = "",
        burn_rate: BurnRate = BurnRate.SLOW,
        budget_status: BudgetStatus = BudgetStatus.HEALTHY,
        burn_cause: BurnCause = BurnCause.INCIDENT,
        budget_total: float = 100.0,
        budget_consumed: float = 0.0,
        burn_velocity: float = 0.0,
        window_hours: int = 24,
        description: str = "",
    ) -> ErrorBudgetBurnRecord:
        record = ErrorBudgetBurnRecord(
            service_id=service_id,
            burn_rate=burn_rate,
            budget_status=budget_status,
            burn_cause=burn_cause,
            budget_total=budget_total,
            budget_consumed=budget_consumed,
            burn_velocity=burn_velocity,
            window_hours=window_hours,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "error_budget_burn_intelligence.record_added",
            record_id=record.id,
            service_id=service_id,
        )
        return record

    def process(self, key: str) -> ErrorBudgetBurnAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        points = sum(1 for r in self._records if r.service_id == rec.service_id)
        remaining = round(
            ((rec.budget_total - rec.budget_consumed) / rec.budget_total * 100)
            if rec.budget_total
            else 0.0,
            2,
        )
        accelerated = rec.burn_rate == BurnRate.FAST
        analysis = ErrorBudgetBurnAnalysis(
            service_id=rec.service_id,
            remaining_pct=remaining,
            burn_rate=rec.burn_rate,
            accelerated=accelerated,
            data_points=points,
            description=f"Service {rec.service_id} budget remaining {remaining}%",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ErrorBudgetBurnReport:
        by_br: dict[str, int] = {}
        by_bs: dict[str, int] = {}
        by_bc: dict[str, int] = {}
        remainings: list[float] = []
        for r in self._records:
            k = r.burn_rate.value
            by_br[k] = by_br.get(k, 0) + 1
            k2 = r.budget_status.value
            by_bs[k2] = by_bs.get(k2, 0) + 1
            k3 = r.burn_cause.value
            by_bc[k3] = by_bc.get(k3, 0) + 1
            if r.budget_total:
                remainings.append((r.budget_total - r.budget_consumed) / r.budget_total * 100)
        avg = round(sum(remainings) / len(remainings), 2) if remainings else 0.0
        exhausted = list(
            {
                r.service_id
                for r in self._records
                if r.budget_status in (BudgetStatus.EXHAUSTED, BudgetStatus.CRITICAL)
            }
        )[:10]
        recs: list[str] = []
        if exhausted:
            recs.append(f"{len(exhausted)} services with exhausted/critical budget")
        if not recs:
            recs.append("All error budgets within healthy range")
        return ErrorBudgetBurnReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_budget_remaining=avg,
            by_burn_rate=by_br,
            by_budget_status=by_bs,
            by_burn_cause=by_bc,
            exhausted_services=exhausted,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        br_dist: dict[str, int] = {}
        for r in self._records:
            k = r.burn_rate.value
            br_dist[k] = br_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "burn_rate_distribution": br_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("error_budget_burn_intelligence.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_burn_rate_trajectory(
        self,
    ) -> list[dict[str, Any]]:
        """Aggregate burn rate trajectory per service."""
        svc_data: dict[str, list[float]] = {}
        svc_status: dict[str, str] = {}
        for r in self._records:
            svc_data.setdefault(r.service_id, []).append(r.burn_velocity)
            svc_status[r.service_id] = r.budget_status.value
        results: list[dict[str, Any]] = []
        for sid, velocities in svc_data.items():
            avg = round(sum(velocities) / len(velocities), 2)
            results.append(
                {
                    "service_id": sid,
                    "budget_status": svc_status[sid],
                    "avg_burn_velocity": avg,
                    "data_points": len(velocities),
                }
            )
        results.sort(key=lambda x: x["avg_burn_velocity"], reverse=True)
        return results

    def detect_accelerated_burn(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with accelerated burn rates."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.burn_rate == BurnRate.FAST and r.service_id not in seen:
                seen.add(r.service_id)
                remaining = round(
                    ((r.budget_total - r.budget_consumed) / r.budget_total * 100)
                    if r.budget_total
                    else 0.0,
                    2,
                )
                results.append(
                    {
                        "service_id": r.service_id,
                        "burn_cause": r.burn_cause.value,
                        "burn_velocity": r.burn_velocity,
                        "remaining_pct": remaining,
                    }
                )
        results.sort(key=lambda x: x["burn_velocity"], reverse=True)
        return results

    def rank_services_by_budget_remaining(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all services by remaining budget."""
        svc_data: dict[str, float] = {}
        svc_totals: dict[str, float] = {}
        for r in self._records:
            svc_data[r.service_id] = r.budget_consumed
            svc_totals[r.service_id] = r.budget_total
        results: list[dict[str, Any]] = []
        for sid, consumed in svc_data.items():
            total = svc_totals[sid]
            remaining = round(((total - consumed) / total * 100) if total else 0.0, 2)
            results.append(
                {
                    "service_id": sid,
                    "remaining_pct": remaining,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["remaining_pct"])
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
