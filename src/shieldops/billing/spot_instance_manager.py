"""Spot Instance Manager — manage and optimize spot instance usage."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SpotStrategy(StrEnum):
    LOWEST_PRICE = "lowest_price"
    CAPACITY_OPTIMIZED = "capacity_optimized"
    DIVERSIFIED = "diversified"
    PRICE_CAPACITY = "price_capacity"
    CUSTOM = "custom"


class InstanceFamily(StrEnum):
    GENERAL = "general"
    COMPUTE = "compute"
    MEMORY = "memory"
    STORAGE = "storage"
    ACCELERATED = "accelerated"


class InterruptionBehavior(StrEnum):
    TERMINATE = "terminate"
    STOP = "stop"
    HIBERNATE = "hibernate"
    REBALANCE = "rebalance"
    MIGRATE = "migrate"


# --- Models ---


class SpotInstanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    spot_strategy: SpotStrategy = SpotStrategy.CAPACITY_OPTIMIZED
    instance_family: InstanceFamily = InstanceFamily.GENERAL
    interruption_behavior: InterruptionBehavior = InterruptionBehavior.TERMINATE
    spot_price: float = 0.0
    on_demand_price: float = 0.0
    savings_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SpotAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    spot_strategy: SpotStrategy = SpotStrategy.CAPACITY_OPTIMIZED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SpotInstanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_savings_count: int = 0
    avg_savings_pct: float = 0.0
    by_spot_strategy: dict[str, int] = Field(default_factory=dict)
    by_instance_family: dict[str, int] = Field(default_factory=dict)
    by_interruption_behavior: dict[str, int] = Field(default_factory=dict)
    top_opportunities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SpotInstanceManager:
    """Manage and optimize spot instance usage for maximum cost savings."""

    def __init__(
        self,
        max_records: int = 200000,
        savings_threshold: float = 40.0,
    ) -> None:
        self._max_records = max_records
        self._savings_threshold = savings_threshold
        self._records: list[SpotInstanceRecord] = []
        self._analyses: list[SpotAnalysis] = []
        logger.info(
            "spot_instance_manager.initialized",
            max_records=max_records,
            savings_threshold=savings_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_spot_instance(
        self,
        spot_strategy: SpotStrategy = SpotStrategy.CAPACITY_OPTIMIZED,
        instance_family: InstanceFamily = InstanceFamily.GENERAL,
        interruption_behavior: InterruptionBehavior = InterruptionBehavior.TERMINATE,
        spot_price: float = 0.0,
        on_demand_price: float = 0.0,
        savings_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SpotInstanceRecord:
        record = SpotInstanceRecord(
            spot_strategy=spot_strategy,
            instance_family=instance_family,
            interruption_behavior=interruption_behavior,
            spot_price=spot_price,
            on_demand_price=on_demand_price,
            savings_pct=savings_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "spot_instance_manager.spot_recorded",
            record_id=record.id,
            spot_strategy=spot_strategy.value,
            savings_pct=savings_pct,
        )
        return record

    def get_spot_instance(self, record_id: str) -> SpotInstanceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_spot_instances(
        self,
        spot_strategy: SpotStrategy | None = None,
        instance_family: InstanceFamily | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SpotInstanceRecord]:
        results = list(self._records)
        if spot_strategy is not None:
            results = [r for r in results if r.spot_strategy == spot_strategy]
        if instance_family is not None:
            results = [r for r in results if r.instance_family == instance_family]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        spot_strategy: SpotStrategy = SpotStrategy.CAPACITY_OPTIMIZED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SpotAnalysis:
        analysis = SpotAnalysis(
            spot_strategy=spot_strategy,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "spot_instance_manager.analysis_added",
            spot_strategy=spot_strategy.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_strategy_distribution(self) -> dict[str, Any]:
        """Group by spot_strategy; return count and avg savings_pct."""
        strat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.spot_strategy.value
            strat_data.setdefault(key, []).append(r.savings_pct)
        result: dict[str, Any] = {}
        for strat, savings in strat_data.items():
            result[strat] = {
                "count": len(savings),
                "avg_savings_pct": round(sum(savings) / len(savings), 2),
            }
        return result

    def identify_high_savings_spots(self) -> list[dict[str, Any]]:
        """Return records where savings_pct >= savings_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.savings_pct >= self._savings_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "spot_strategy": r.spot_strategy.value,
                        "savings_pct": r.savings_pct,
                        "spot_price": r.spot_price,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["savings_pct"], reverse=True)

    def rank_by_savings(self) -> list[dict[str, Any]]:
        """Group by service, avg savings_pct, sort descending."""
        svc_savings: dict[str, list[float]] = {}
        for r in self._records:
            svc_savings.setdefault(r.service, []).append(r.savings_pct)
        results: list[dict[str, Any]] = [
            {
                "service": svc,
                "avg_savings_pct": round(sum(s) / len(s), 2),
            }
            for svc, s in svc_savings.items()
        ]
        results.sort(key=lambda x: x["avg_savings_pct"], reverse=True)
        return results

    def detect_savings_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
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

    def generate_report(self) -> SpotInstanceReport:
        by_strategy: dict[str, int] = {}
        by_family: dict[str, int] = {}
        by_behavior: dict[str, int] = {}
        for r in self._records:
            by_strategy[r.spot_strategy.value] = by_strategy.get(r.spot_strategy.value, 0) + 1
            by_family[r.instance_family.value] = by_family.get(r.instance_family.value, 0) + 1
            by_behavior[r.interruption_behavior.value] = (
                by_behavior.get(r.interruption_behavior.value, 0) + 1
            )
        high_savings_count = sum(
            1 for r in self._records if r.savings_pct >= self._savings_threshold
        )
        savings = [r.savings_pct for r in self._records]
        avg_savings_pct = round(sum(savings) / len(savings), 2) if savings else 0.0
        opps = self.identify_high_savings_spots()
        top_opportunities = [o["record_id"] for o in opps[:5]]
        recs: list[str] = []
        if high_savings_count > 0:
            recs.append(f"{high_savings_count} spot instance(s) achieving high savings")
        if avg_savings_pct < self._savings_threshold and self._records:
            recs.append(
                f"Avg spot savings {avg_savings_pct}% below target ({self._savings_threshold}%)"
            )
        if not recs:
            recs.append("Spot instance management is healthy")
        return SpotInstanceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_savings_count=high_savings_count,
            avg_savings_pct=avg_savings_pct,
            by_spot_strategy=by_strategy,
            by_instance_family=by_family,
            by_interruption_behavior=by_behavior,
            top_opportunities=top_opportunities,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("spot_instance_manager.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        strat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.spot_strategy.value
            strat_dist[key] = strat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "savings_threshold": self._savings_threshold,
            "spot_strategy_distribution": strat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
