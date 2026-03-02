"""Budget-Aware Autoscaler — autoscale resources with budget awareness."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ScalingStrategy(StrEnum):
    COST_OPTIMIZED = "cost_optimized"
    PERFORMANCE_FIRST = "performance_first"
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"
    AGGRESSIVE = "aggressive"


class BudgetStatus(StrEnum):
    UNDER_BUDGET = "under_budget"
    AT_THRESHOLD = "at_threshold"
    OVER_BUDGET = "over_budget"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


class ScalingAction(StrEnum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"
    MAINTAIN = "maintain"


# --- Models ---


class AutoscalingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scaling_strategy: ScalingStrategy = ScalingStrategy.BALANCED
    budget_status: BudgetStatus = BudgetStatus.UNDER_BUDGET
    scaling_action: ScalingAction = ScalingAction.MAINTAIN
    budget_used_pct: float = 0.0
    resource_count: int = 0
    cost_impact: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AutoscalingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scaling_strategy: ScalingStrategy = ScalingStrategy.BALANCED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BudgetAutoscalerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    over_budget_count: int = 0
    avg_budget_used_pct: float = 0.0
    by_scaling_strategy: dict[str, int] = Field(default_factory=dict)
    by_budget_status: dict[str, int] = Field(default_factory=dict)
    by_scaling_action: dict[str, int] = Field(default_factory=dict)
    top_over_budget: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class BudgetAwareAutoscaler:
    """Autoscale resources while respecting budget constraints and thresholds."""

    def __init__(
        self,
        max_records: int = 200000,
        budget_alert_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._budget_alert_threshold = budget_alert_threshold
        self._records: list[AutoscalingRecord] = []
        self._analyses: list[AutoscalingAnalysis] = []
        logger.info(
            "budget_aware_autoscaler.initialized",
            max_records=max_records,
            budget_alert_threshold=budget_alert_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_scaling_event(
        self,
        scaling_strategy: ScalingStrategy = ScalingStrategy.BALANCED,
        budget_status: BudgetStatus = BudgetStatus.UNDER_BUDGET,
        scaling_action: ScalingAction = ScalingAction.MAINTAIN,
        budget_used_pct: float = 0.0,
        resource_count: int = 0,
        cost_impact: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AutoscalingRecord:
        record = AutoscalingRecord(
            scaling_strategy=scaling_strategy,
            budget_status=budget_status,
            scaling_action=scaling_action,
            budget_used_pct=budget_used_pct,
            resource_count=resource_count,
            cost_impact=cost_impact,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "budget_aware_autoscaler.event_recorded",
            record_id=record.id,
            scaling_action=scaling_action.value,
            budget_used_pct=budget_used_pct,
        )
        return record

    def get_scaling_event(self, record_id: str) -> AutoscalingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_scaling_events(
        self,
        scaling_strategy: ScalingStrategy | None = None,
        budget_status: BudgetStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AutoscalingRecord]:
        results = list(self._records)
        if scaling_strategy is not None:
            results = [r for r in results if r.scaling_strategy == scaling_strategy]
        if budget_status is not None:
            results = [r for r in results if r.budget_status == budget_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        scaling_strategy: ScalingStrategy = ScalingStrategy.BALANCED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AutoscalingAnalysis:
        analysis = AutoscalingAnalysis(
            scaling_strategy=scaling_strategy,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "budget_aware_autoscaler.analysis_added",
            scaling_strategy=scaling_strategy.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_strategy_distribution(self) -> dict[str, Any]:
        """Group by scaling_strategy; return count and avg budget_used_pct."""
        strat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.scaling_strategy.value
            strat_data.setdefault(key, []).append(r.budget_used_pct)
        result: dict[str, Any] = {}
        for strat, budgets in strat_data.items():
            result[strat] = {
                "count": len(budgets),
                "avg_budget_used_pct": round(sum(budgets) / len(budgets), 2),
            }
        return result

    def identify_over_budget_events(self) -> list[dict[str, Any]]:
        """Return records where budget_status is OVER_BUDGET, CRITICAL, or EXHAUSTED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.budget_status in (
                BudgetStatus.OVER_BUDGET,
                BudgetStatus.CRITICAL,
                BudgetStatus.EXHAUSTED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "budget_status": r.budget_status.value,
                        "budget_used_pct": r.budget_used_pct,
                        "cost_impact": r.cost_impact,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["budget_used_pct"], reverse=True)

    def rank_by_budget_usage(self) -> list[dict[str, Any]]:
        """Group by service, avg budget_used_pct, sort descending."""
        svc_budgets: dict[str, list[float]] = {}
        for r in self._records:
            svc_budgets.setdefault(r.service, []).append(r.budget_used_pct)
        results: list[dict[str, Any]] = [
            {
                "service": svc,
                "avg_budget_used_pct": round(sum(b) / len(b), 2),
            }
            for svc, b in svc_budgets.items()
        ]
        results.sort(key=lambda x: x["avg_budget_used_pct"], reverse=True)
        return results

    def detect_budget_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
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

    def generate_report(self) -> BudgetAutoscalerReport:
        by_strategy: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_strategy[r.scaling_strategy.value] = by_strategy.get(r.scaling_strategy.value, 0) + 1
            by_status[r.budget_status.value] = by_status.get(r.budget_status.value, 0) + 1
            by_action[r.scaling_action.value] = by_action.get(r.scaling_action.value, 0) + 1
        over_budget_count = sum(
            1
            for r in self._records
            if r.budget_status
            in (
                BudgetStatus.OVER_BUDGET,
                BudgetStatus.CRITICAL,
                BudgetStatus.EXHAUSTED,
            )
        )
        budgets = [r.budget_used_pct for r in self._records]
        avg_budget_used_pct = round(sum(budgets) / len(budgets), 2) if budgets else 0.0
        over_list = self.identify_over_budget_events()
        top_over_budget = [o["record_id"] for o in over_list[:5]]
        recs: list[str] = []
        if over_budget_count > 0:
            recs.append(f"{over_budget_count} scaling event(s) triggered over-budget alerts")
        if avg_budget_used_pct >= self._budget_alert_threshold and self._records:
            recs.append(
                f"Avg budget usage {avg_budget_used_pct}% exceeds alert threshold "
                f"({self._budget_alert_threshold}%)"
            )
        if not recs:
            recs.append("Budget-aware autoscaling is healthy")
        return BudgetAutoscalerReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            over_budget_count=over_budget_count,
            avg_budget_used_pct=avg_budget_used_pct,
            by_scaling_strategy=by_strategy,
            by_budget_status=by_status,
            by_scaling_action=by_action,
            top_over_budget=top_over_budget,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("budget_aware_autoscaler.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        strat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.scaling_strategy.value
            strat_dist[key] = strat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "budget_alert_threshold": self._budget_alert_threshold,
            "scaling_strategy_distribution": strat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
