"""Resource Budget Manager

Track and manage experiment resource budgets with
allocation strategies and exhaustion forecasting.
"""

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
    GPU = "gpu"
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"


class AllocationStrategy(StrEnum):
    FIXED = "fixed"
    ELASTIC = "elastic"
    PRIORITY = "priority"
    FAIR_SHARE = "fair_share"


class BudgetStatus(StrEnum):
    UNDER_BUDGET = "under_budget"
    AT_LIMIT = "at_limit"
    OVER_BUDGET = "over_budget"
    EXHAUSTED = "exhausted"


# --- Models ---


class BudgetRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_type: ResourceType = ResourceType.GPU
    strategy: AllocationStrategy = AllocationStrategy.ELASTIC
    status: BudgetStatus = BudgetStatus.UNDER_BUDGET
    allocated: float = 0.0
    consumed: float = 0.0
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BudgetAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_type: ResourceType = ResourceType.GPU
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BudgetReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    over_budget_count: int = 0
    avg_utilization: float = 0.0
    by_resource: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResourceBudgetManager:
    """Track and manage experiment resource budgets
    with allocation and exhaustion forecasting.
    """

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[BudgetRecord] = []
        self._analyses: dict[str, BudgetAnalysis] = {}
        logger.info(
            "resource_budget_manager.initialized",
            max_records=max_records,
        )

    def record_item(
        self,
        name: str = "",
        resource_type: ResourceType = ResourceType.GPU,
        strategy: AllocationStrategy = (AllocationStrategy.ELASTIC),
        status: BudgetStatus = BudgetStatus.UNDER_BUDGET,
        allocated: float = 0.0,
        consumed: float = 0.0,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> BudgetRecord:
        record = BudgetRecord(
            name=name,
            resource_type=resource_type,
            strategy=strategy,
            status=status,
            allocated=allocated,
            consumed=consumed,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "resource_budget_manager.item_recorded",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.id == key]
        if not matching:
            return {"key": key, "status": "no_data"}
        rec = matching[0]
        util = round(rec.consumed / rec.allocated, 4) if rec.allocated > 0 else 0.0
        analysis = BudgetAnalysis(
            name=rec.name,
            resource_type=rec.resource_type,
            analysis_score=util,
            description=(f"Budget {rec.name} utilization={util:.2%}"),
        )
        self._analyses[key] = analysis
        return {
            "key": key,
            "analysis_id": analysis.id,
            "utilization": util,
        }

    def generate_report(self) -> BudgetReport:
        by_res: dict[str, int] = {}
        by_strat: dict[str, int] = {}
        by_stat: dict[str, int] = {}
        over_budget = 0
        utils: list[float] = []
        for r in self._records:
            rt = r.resource_type.value
            by_res[rt] = by_res.get(rt, 0) + 1
            s = r.strategy.value
            by_strat[s] = by_strat.get(s, 0) + 1
            st = r.status.value
            by_stat[st] = by_stat.get(st, 0) + 1
            if r.status in (
                BudgetStatus.OVER_BUDGET,
                BudgetStatus.EXHAUSTED,
            ):
                over_budget += 1
            if r.allocated > 0:
                utils.append(r.consumed / r.allocated)
        avg_util = round(sum(utils) / len(utils), 4) if utils else 0.0
        recs: list[str] = []
        total = len(self._records)
        if total > 0 and over_budget / total > 0.2:
            recs.append("High over-budget rate — review allocation strategy")
        if not recs:
            recs.append("Budget management is healthy")
        return BudgetReport(
            total_records=total,
            total_analyses=len(self._analyses),
            over_budget_count=over_budget,
            avg_utilization=avg_util,
            by_resource=by_res,
            by_strategy=by_strat,
            by_status=by_stat,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        res_dist: dict[str, int] = {}
        for r in self._records:
            k = r.resource_type.value
            res_dist[k] = res_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "resource_distribution": res_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("resource_budget_manager.cleared")
        return {"status": "cleared"}

    # --- Domain methods ---

    def allocate_experiment_budget(self, name: str) -> dict[str, Any]:
        """Compute allocation for an experiment."""
        matching = [r for r in self._records if r.name == name]
        if not matching:
            return {"name": name, "status": "no_data"}
        total_alloc = sum(r.allocated for r in matching)
        total_consumed = sum(r.consumed for r in matching)
        return {
            "name": name,
            "total_allocated": round(total_alloc, 4),
            "total_consumed": round(total_consumed, 4),
            "remaining": round(total_alloc - total_consumed, 4),
        }

    def compute_utilization_efficiency(self, name: str) -> dict[str, Any]:
        """Compute utilization efficiency."""
        matching = [r for r in self._records if r.name == name]
        if not matching:
            return {"name": name, "status": "no_data"}
        utils = []
        for r in matching:
            if r.allocated > 0:
                utils.append(r.consumed / r.allocated)
        if not utils:
            return {"name": name, "efficiency": 0.0}
        return {
            "name": name,
            "efficiency": round(sum(utils) / len(utils), 4),
            "sample_count": len(utils),
        }

    def forecast_budget_exhaustion(self, name: str) -> dict[str, Any]:
        """Forecast when budget will be exhausted."""
        matching = [r for r in self._records if r.name == name]
        if not matching:
            return {"name": name, "status": "no_data"}
        latest = matching[-1]
        if latest.allocated <= 0:
            return {
                "name": name,
                "status": "no_allocation",
            }
        rate = latest.consumed / latest.allocated
        remaining_pct = max(0, 1 - rate)
        return {
            "name": name,
            "utilization_rate": round(rate, 4),
            "remaining_pct": round(remaining_pct, 4),
            "risk": ("high" if remaining_pct < 0.1 else "low"),
        }
