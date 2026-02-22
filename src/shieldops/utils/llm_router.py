"""LLM Router — routes requests to optimal model based on task complexity.

Reduces cost by routing simple tasks to cheaper models while preserving
quality for complex operations that require the most capable model.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class TaskComplexity(StrEnum):
    """Task complexity levels for LLM routing."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class ModelTier(BaseModel):
    """Configuration for a model tier."""

    provider: str  # anthropic, openai
    model: str
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    max_tokens: int = 4096


class UsageRecord(BaseModel):
    """Record of a single LLM usage."""

    request_id: str = ""
    complexity: TaskComplexity = TaskComplexity.MODERATE
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    latency_ms: int = 0
    agent_type: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UsageStats(BaseModel):
    """Aggregated usage statistics."""

    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_estimated_cost: float = 0.0
    by_model: dict[str, dict[str, Any]] = Field(default_factory=dict)
    by_complexity: dict[str, dict[str, Any]] = Field(default_factory=dict)
    by_agent: dict[str, dict[str, Any]] = Field(default_factory=dict)


# Default model configurations per complexity tier
DEFAULT_MODEL_TIERS: dict[TaskComplexity, ModelTier] = {
    TaskComplexity.SIMPLE: ModelTier(
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        cost_per_1k_input=0.001,
        cost_per_1k_output=0.005,
        max_tokens=4096,
    ),
    TaskComplexity.MODERATE: ModelTier(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        max_tokens=4096,
    ),
    TaskComplexity.COMPLEX: ModelTier(
        provider="anthropic",
        model="claude-opus-4-20250514",
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        max_tokens=4096,
    ),
}


class LLMRouter:
    """Routes LLM requests to optimal model based on task complexity.

    Classifies task complexity using heuristics (prompt length, tool use,
    structured output requirements) and routes to the appropriate model tier.
    Tracks usage and cost per request.
    """

    # Heuristic thresholds for complexity classification
    SIMPLE_MAX_TOKENS = 200
    MODERATE_MAX_TOKENS = 1000

    # Keywords indicating higher complexity
    COMPLEX_KEYWORDS = {
        "analyze",
        "correlate",
        "hypothesis",
        "root cause",
        "diagnosis",
        "architectural",
        "security audit",
        "compliance",
        "multi-step",
    }

    SIMPLE_KEYWORDS = {
        "classify",
        "categorize",
        "extract",
        "summarize",
        "format",
        "parse",
        "validate",
    }

    def __init__(
        self,
        model_tiers: dict[TaskComplexity, ModelTier] | None = None,
        enabled: bool = True,
    ) -> None:
        self._tiers = model_tiers or dict(DEFAULT_MODEL_TIERS)
        self._enabled = enabled
        self._usage_records: list[UsageRecord] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    def classify_complexity(
        self,
        prompt: str,
        requires_tool_use: bool = False,
        requires_structured_output: bool = False,
    ) -> TaskComplexity:
        """Classify the complexity of an LLM task.

        Heuristic-based classification using:
        - Token count (approximated as chars / 4)
        - Presence of complexity-indicating keywords
        - Whether tool use or structured output is required
        """
        if not prompt:
            return TaskComplexity.SIMPLE

        estimated_tokens = len(prompt) // 4
        prompt_lower = prompt.lower()

        # Check for complex keywords
        has_complex_keywords = any(kw in prompt_lower for kw in self.COMPLEX_KEYWORDS)
        has_simple_keywords = any(kw in prompt_lower for kw in self.SIMPLE_KEYWORDS)

        # Complex: long prompt + complex keywords or tool use
        if estimated_tokens > self.MODERATE_MAX_TOKENS or (
            has_complex_keywords and requires_tool_use
        ):
            return TaskComplexity.COMPLEX

        # Simple: short prompt + simple keywords, no tools
        if (
            estimated_tokens <= self.SIMPLE_MAX_TOKENS
            and not requires_tool_use
            and not has_complex_keywords
            and (has_simple_keywords or not requires_structured_output)
        ):
            return TaskComplexity.SIMPLE

        return TaskComplexity.MODERATE

    def get_model(
        self,
        complexity: TaskComplexity | None = None,
        prompt: str = "",
        requires_tool_use: bool = False,
        requires_structured_output: bool = False,
    ) -> ModelTier:
        """Get the optimal model for the given task.

        Args:
            complexity: Explicit complexity override.
            prompt: Task prompt (used for classification if complexity not given).
            requires_tool_use: Whether the task needs tool calling.
            requires_structured_output: Whether the task needs structured JSON output.

        Returns:
            The model tier to use.
        """
        if complexity is None:
            complexity = self.classify_complexity(
                prompt=prompt,
                requires_tool_use=requires_tool_use,
                requires_structured_output=requires_structured_output,
            )

        return self._tiers.get(complexity, self._tiers[TaskComplexity.MODERATE])

    def record_usage(
        self,
        request_id: str,
        complexity: TaskComplexity,
        model: str,
        provider: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
        agent_type: str = "",
    ) -> UsageRecord:
        """Record LLM usage for cost tracking."""
        tier = None
        for t in self._tiers.values():
            if t.model == model:
                tier = t
                break

        estimated_cost = 0.0
        if tier:
            estimated_cost = (
                input_tokens / 1000 * tier.cost_per_1k_input
                + output_tokens / 1000 * tier.cost_per_1k_output
            )

        record = UsageRecord(
            request_id=request_id,
            complexity=complexity,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=round(estimated_cost, 6),
            latency_ms=latency_ms,
            agent_type=agent_type,
        )
        self._usage_records.append(record)

        logger.debug(
            "llm_usage_recorded",
            model=model,
            complexity=complexity,
            cost=estimated_cost,
        )
        return record

    def get_usage_stats(self) -> UsageStats:
        """Get aggregated usage statistics."""
        stats = UsageStats()

        for record in self._usage_records:
            stats.total_requests += 1
            stats.total_input_tokens += record.input_tokens
            stats.total_output_tokens += record.output_tokens
            stats.total_estimated_cost += record.estimated_cost

            # By model
            if record.model not in stats.by_model:
                stats.by_model[record.model] = {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0,
                }
            stats.by_model[record.model]["requests"] += 1
            stats.by_model[record.model]["input_tokens"] += record.input_tokens
            stats.by_model[record.model]["output_tokens"] += record.output_tokens
            stats.by_model[record.model]["cost"] += record.estimated_cost

            # By complexity
            ckey = record.complexity.value
            if ckey not in stats.by_complexity:
                stats.by_complexity[ckey] = {"requests": 0, "cost": 0.0}
            stats.by_complexity[ckey]["requests"] += 1
            stats.by_complexity[ckey]["cost"] += record.estimated_cost

            # By agent
            if record.agent_type:
                if record.agent_type not in stats.by_agent:
                    stats.by_agent[record.agent_type] = {"requests": 0, "cost": 0.0}
                stats.by_agent[record.agent_type]["requests"] += 1
                stats.by_agent[record.agent_type]["cost"] += record.estimated_cost

        stats.total_estimated_cost = round(stats.total_estimated_cost, 6)
        return stats

    def get_cost_breakdown(
        self,
        agent_type: str | None = None,
    ) -> dict[str, Any]:
        """Get cost breakdown by model and time period."""
        records = self._usage_records
        if agent_type:
            records = [r for r in records if r.agent_type == agent_type]

        breakdown: dict[str, Any] = {
            "total_cost": 0.0,
            "total_requests": len(records),
            "by_model": {},
        }

        for record in records:
            breakdown["total_cost"] += record.estimated_cost
            if record.model not in breakdown["by_model"]:
                breakdown["by_model"][record.model] = {
                    "requests": 0,
                    "cost": 0.0,
                    "avg_latency_ms": 0,
                }
            entry = breakdown["by_model"][record.model]
            entry["requests"] += 1
            entry["cost"] += record.estimated_cost
            entry["avg_latency_ms"] = (
                entry["avg_latency_ms"] * (entry["requests"] - 1) + record.latency_ms
            ) / entry["requests"]

        breakdown["total_cost"] = round(breakdown["total_cost"], 6)
        return breakdown
