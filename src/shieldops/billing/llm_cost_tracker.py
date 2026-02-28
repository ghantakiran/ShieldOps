"""LLM Token Cost Tracker — track AI/LLM API token usage and costs per agent and service."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LLMProvider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    COHERE = "cohere"
    LOCAL = "local"


class TokenCategory(StrEnum):
    INPUT = "input"
    OUTPUT = "output"
    EMBEDDING = "embedding"
    FINE_TUNING = "fine_tuning"
    CACHED = "cached"


class CostTrend(StrEnum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class LLMCostRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    provider: LLMProvider = LLMProvider.ANTHROPIC
    category: TokenCategory = TokenCategory.INPUT
    token_count: int = 0
    cost_usd: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ProviderCostBreakdown(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    provider_name: str = ""
    provider: LLMProvider = LLMProvider.ANTHROPIC
    category: TokenCategory = TokenCategory.INPUT
    total_tokens: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LLMCostReport(BaseModel):
    total_records: int = 0
    total_breakdowns: int = 0
    avg_cost_usd: float = 0.0
    by_provider: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    high_cost_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class LLMTokenCostTracker:
    """Track AI/LLM API token usage and costs per agent and service."""

    def __init__(
        self,
        max_records: int = 200000,
        high_cost_threshold: float = 100.0,
    ) -> None:
        self._max_records = max_records
        self._high_cost_threshold = high_cost_threshold
        self._records: list[LLMCostRecord] = []
        self._breakdowns: list[ProviderCostBreakdown] = []
        logger.info(
            "llm_cost_tracker.initialized",
            max_records=max_records,
            high_cost_threshold=high_cost_threshold,
        )

    # -- record / get / list ---------------------------------------------

    def record_cost(
        self,
        agent_name: str,
        provider: LLMProvider = LLMProvider.ANTHROPIC,
        category: TokenCategory = TokenCategory.INPUT,
        token_count: int = 0,
        cost_usd: float = 0.0,
        details: str = "",
    ) -> LLMCostRecord:
        record = LLMCostRecord(
            agent_name=agent_name,
            provider=provider,
            category=category,
            token_count=token_count,
            cost_usd=cost_usd,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "llm_cost_tracker.cost_recorded",
            record_id=record.id,
            agent_name=agent_name,
            provider=provider.value,
        )
        return record

    def get_cost(self, record_id: str) -> LLMCostRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_costs(
        self,
        agent_name: str | None = None,
        provider: LLMProvider | None = None,
        limit: int = 50,
    ) -> list[LLMCostRecord]:
        results = list(self._records)
        if agent_name is not None:
            results = [r for r in results if r.agent_name == agent_name]
        if provider is not None:
            results = [r for r in results if r.provider == provider]
        return results[-limit:]

    def add_breakdown(
        self,
        provider_name: str,
        provider: LLMProvider = LLMProvider.ANTHROPIC,
        category: TokenCategory = TokenCategory.INPUT,
        total_tokens: int = 0,
        description: str = "",
    ) -> ProviderCostBreakdown:
        breakdown = ProviderCostBreakdown(
            provider_name=provider_name,
            provider=provider,
            category=category,
            total_tokens=total_tokens,
            description=description,
        )
        self._breakdowns.append(breakdown)
        if len(self._breakdowns) > self._max_records:
            self._breakdowns = self._breakdowns[-self._max_records :]
        logger.info(
            "llm_cost_tracker.breakdown_added",
            provider_name=provider_name,
            provider=provider.value,
        )
        return breakdown

    # -- domain operations -----------------------------------------------

    def analyze_agent_costs(self, agent_name: str) -> dict[str, Any]:
        """Analyze costs for a specific agent."""
        records = [r for r in self._records if r.agent_name == agent_name]
        if not records:
            return {
                "agent_name": agent_name,
                "status": "no_data",
            }
        total_cost = sum(r.cost_usd for r in records)
        avg_cost = round(total_cost / len(records), 2)
        return {
            "agent_name": agent_name,
            "total_cost_usd": round(total_cost, 2),
            "avg_cost_usd": avg_cost,
            "record_count": len(records),
            "meets_threshold": avg_cost <= self._high_cost_threshold,
        }

    def identify_high_cost_agents(self) -> list[dict[str, Any]]:
        """Find agents with more than one cost record above threshold."""
        by_agent: dict[str, list[float]] = {}
        for r in self._records:
            by_agent.setdefault(r.agent_name, []).append(r.cost_usd)
        results: list[dict[str, Any]] = []
        for agent, costs in by_agent.items():
            high_count = sum(1 for c in costs if c > self._high_cost_threshold)
            if high_count > 1:
                results.append(
                    {
                        "agent_name": agent,
                        "high_cost_count": high_count,
                        "total_cost_usd": round(sum(costs), 2),
                        "avg_cost_usd": round(sum(costs) / len(costs), 2),
                    }
                )
        results.sort(key=lambda x: x["total_cost_usd"], reverse=True)
        return results

    def rank_by_total_cost(self) -> list[dict[str, Any]]:
        """Rank agents by average cost (descending)."""
        by_agent: dict[str, list[float]] = {}
        for r in self._records:
            by_agent.setdefault(r.agent_name, []).append(r.cost_usd)
        results: list[dict[str, Any]] = []
        for agent, costs in by_agent.items():
            avg_cost = round(sum(costs) / len(costs), 2)
            results.append(
                {
                    "agent_name": agent,
                    "avg_cost_usd": avg_cost,
                    "record_count": len(costs),
                }
            )
        results.sort(key=lambda x: x["avg_cost_usd"], reverse=True)
        return results

    def detect_cost_trends(self) -> list[dict[str, Any]]:
        """Detect cost trends for agents with more than 3 records."""
        by_agent: dict[str, list[LLMCostRecord]] = {}
        for r in self._records:
            by_agent.setdefault(r.agent_name, []).append(r)
        results: list[dict[str, Any]] = []
        for agent, records in by_agent.items():
            if len(records) <= 3:
                continue
            mid = len(records) // 2
            older_avg = sum(r.cost_usd for r in records[:mid]) / mid
            recent_avg = sum(r.cost_usd for r in records[mid:]) / (len(records) - mid)
            if older_avg == 0:
                trend = CostTrend.INSUFFICIENT_DATA
            else:
                change_pct = ((recent_avg - older_avg) / older_avg) * 100
                if change_pct > 20:
                    trend = CostTrend.INCREASING
                elif change_pct < -20:
                    trend = CostTrend.DECREASING
                elif abs(change_pct) <= 20:
                    trend = CostTrend.STABLE
                else:
                    trend = CostTrend.VOLATILE
            results.append(
                {
                    "agent_name": agent,
                    "trend": trend.value,
                    "older_avg_cost": round(older_avg, 2),
                    "recent_avg_cost": round(recent_avg, 2),
                    "record_count": len(records),
                }
            )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> LLMCostReport:
        by_provider: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_provider[r.provider.value] = by_provider.get(r.provider.value, 0) + 1
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
        avg_cost = (
            round(sum(r.cost_usd for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        high_cost = sum(1 for r in self._records if r.cost_usd > self._high_cost_threshold)
        recs: list[str] = []
        if high_cost > 0:
            recs.append(f"{high_cost} record(s) with cost > ${self._high_cost_threshold}")
        if avg_cost > self._high_cost_threshold:
            recs.append(f"Average cost ${avg_cost} exceeds threshold ${self._high_cost_threshold}")
        if not recs:
            recs.append("LLM token costs are within acceptable bounds")
        return LLMCostReport(
            total_records=len(self._records),
            total_breakdowns=len(self._breakdowns),
            avg_cost_usd=avg_cost,
            by_provider=by_provider,
            by_category=by_category,
            high_cost_count=high_cost,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._breakdowns.clear()
        logger.info("llm_cost_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        provider_dist: dict[str, int] = {}
        for r in self._records:
            key = r.provider.value
            provider_dist[key] = provider_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_breakdowns": len(self._breakdowns),
            "high_cost_threshold": self._high_cost_threshold,
            "provider_distribution": provider_dist,
            "unique_agents": len({r.agent_name for r in self._records}),
        }
