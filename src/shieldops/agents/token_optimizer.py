"""Agent Token Optimizer — minimize LLM token usage via compression and caching."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class OptimizationStrategy(StrEnum):
    PROMPT_COMPRESSION = "prompt_compression"
    RESPONSE_CACHING = "response_caching"
    SEMANTIC_DEDUP = "semantic_dedup"
    MODEL_DOWNGRADE = "model_downgrade"
    CONTEXT_PRUNING = "context_pruning"


class TokenSavingsLevel(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"


class CostTier(StrEnum):
    PREMIUM = "premium"
    STANDARD = "standard"
    ECONOMY = "economy"
    FREE_TIER = "free_tier"
    CACHED = "cached"


# --- Models ---


class TokenUsageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.PROMPT_COMPRESSION
    savings_level: TokenSavingsLevel = TokenSavingsLevel.MODERATE
    cost_tier: CostTier = CostTier.STANDARD
    tokens_saved: int = 0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class OptimizationResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    result_label: str = ""
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.PROMPT_COMPRESSION
    savings_level: TokenSavingsLevel = TokenSavingsLevel.GOOD
    savings_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class TokenOptimizerReport(BaseModel):
    total_records: int = 0
    total_results: int = 0
    avg_savings_pct: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_savings_level: dict[str, int] = Field(default_factory=dict)
    low_savings_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AgentTokenOptimizer:
    """Minimize LLM token usage via prompt compression, caching, and model routing."""

    def __init__(
        self,
        max_records: int = 200000,
        target_savings_pct: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._target_savings_pct = target_savings_pct
        self._records: list[TokenUsageRecord] = []
        self._results: list[OptimizationResult] = []
        logger.info(
            "token_optimizer.initialized",
            max_records=max_records,
            target_savings_pct=target_savings_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_usage(
        self,
        agent_name: str,
        optimization_strategy: OptimizationStrategy = OptimizationStrategy.PROMPT_COMPRESSION,
        savings_level: TokenSavingsLevel = TokenSavingsLevel.MODERATE,
        cost_tier: CostTier = CostTier.STANDARD,
        tokens_saved: int = 0,
        details: str = "",
    ) -> TokenUsageRecord:
        record = TokenUsageRecord(
            agent_name=agent_name,
            optimization_strategy=optimization_strategy,
            savings_level=savings_level,
            cost_tier=cost_tier,
            tokens_saved=tokens_saved,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "token_optimizer.usage_recorded",
            record_id=record.id,
            agent_name=agent_name,
            optimization_strategy=optimization_strategy.value,
        )
        return record

    def get_usage(self, record_id: str) -> TokenUsageRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_usages(
        self,
        agent_name: str | None = None,
        optimization_strategy: OptimizationStrategy | None = None,
        limit: int = 50,
    ) -> list[TokenUsageRecord]:
        results = list(self._records)
        if agent_name is not None:
            results = [r for r in results if r.agent_name == agent_name]
        if optimization_strategy is not None:
            results = [r for r in results if r.optimization_strategy == optimization_strategy]
        return results[-limit:]

    def add_result(
        self,
        result_label: str,
        optimization_strategy: OptimizationStrategy = OptimizationStrategy.PROMPT_COMPRESSION,
        savings_level: TokenSavingsLevel = TokenSavingsLevel.GOOD,
        savings_pct: float = 0.0,
    ) -> OptimizationResult:
        result = OptimizationResult(
            result_label=result_label,
            optimization_strategy=optimization_strategy,
            savings_level=savings_level,
            savings_pct=savings_pct,
        )
        self._results.append(result)
        if len(self._results) > self._max_records:
            self._results = self._results[-self._max_records :]
        logger.info(
            "token_optimizer.result_added",
            result_label=result_label,
            optimization_strategy=optimization_strategy.value,
        )
        return result

    # -- domain operations -----------------------------------------------

    def analyze_agent_savings(self, agent_name: str) -> dict[str, Any]:
        records = [r for r in self._records if r.agent_name == agent_name]
        if not records:
            return {"agent_name": agent_name, "status": "no_data"}
        avg_saved = round(sum(r.tokens_saved for r in records) / len(records), 2)
        good_count = sum(
            1
            for r in records
            if r.savings_level in (TokenSavingsLevel.EXCELLENT, TokenSavingsLevel.GOOD)
        )
        savings_rate = round(good_count / len(records) * 100, 2)
        return {
            "agent_name": agent_name,
            "total_records": len(records),
            "avg_tokens_saved": avg_saved,
            "savings_rate_pct": savings_rate,
            "meets_threshold": savings_rate >= self._target_savings_pct,
        }

    def identify_low_savings_agents(self) -> list[dict[str, Any]]:
        by_agent: dict[str, int] = {}
        for r in self._records:
            if r.savings_level in (TokenSavingsLevel.NONE, TokenSavingsLevel.LOW):
                by_agent[r.agent_name] = by_agent.get(r.agent_name, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in by_agent.items():
            if count > 1:
                results.append({"agent_name": agent, "low_savings_count": count})
        results.sort(key=lambda x: x["low_savings_count"], reverse=True)
        return results

    def rank_by_tokens_saved(self) -> list[dict[str, Any]]:
        by_agent: dict[str, int] = {}
        for r in self._records:
            by_agent[r.agent_name] = by_agent.get(r.agent_name, 0) + r.tokens_saved
        results: list[dict[str, Any]] = []
        for agent, total in by_agent.items():
            results.append(
                {
                    "agent_name": agent,
                    "total_tokens_saved": total,
                }
            )
        results.sort(key=lambda x: x["total_tokens_saved"], reverse=True)
        return results

    def detect_savings_regression(self) -> list[dict[str, Any]]:
        by_agent: dict[str, int] = {}
        for r in self._records:
            if r.savings_level == TokenSavingsLevel.NONE:
                by_agent[r.agent_name] = by_agent.get(r.agent_name, 0) + 1
        results: list[dict[str, Any]] = []
        for agent, count in by_agent.items():
            if count > 3:
                results.append(
                    {
                        "agent_name": agent,
                        "none_count": count,
                        "regressing": True,
                    }
                )
        results.sort(key=lambda x: x["none_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> TokenOptimizerReport:
        by_strategy: dict[str, int] = {}
        by_savings_level: dict[str, int] = {}
        for r in self._records:
            by_strategy[r.optimization_strategy.value] = (
                by_strategy.get(r.optimization_strategy.value, 0) + 1
            )
            by_savings_level[r.savings_level.value] = (
                by_savings_level.get(r.savings_level.value, 0) + 1
            )
        avg_pct = (
            round(
                sum(r.savings_pct for r in self._results) / len(self._results),
                2,
            )
            if self._results
            else 0.0
        )
        low_count = sum(
            1
            for r in self._records
            if r.savings_level in (TokenSavingsLevel.NONE, TokenSavingsLevel.LOW)
        )
        recs: list[str] = []
        if low_count > 0:
            recs.append(f"{low_count} record(s) with low or no token savings")
        if avg_pct < self._target_savings_pct and self._results:
            recs.append(f"Average savings {avg_pct}% below target {self._target_savings_pct}%")
        if not recs:
            recs.append("Token optimization meets targets")
        return TokenOptimizerReport(
            total_records=len(self._records),
            total_results=len(self._results),
            avg_savings_pct=avg_pct,
            by_strategy=by_strategy,
            by_savings_level=by_savings_level,
            low_savings_count=low_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._results.clear()
        logger.info("token_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        strategy_dist: dict[str, int] = {}
        for r in self._records:
            key = r.optimization_strategy.value
            strategy_dist[key] = strategy_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_results": len(self._results),
            "target_savings_pct": self._target_savings_pct,
            "strategy_distribution": strategy_dist,
            "unique_agents": len({r.agent_name for r in self._records}),
        }
