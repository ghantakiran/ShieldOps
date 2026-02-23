"""Agent resource quotas and concurrency limits.

Prevents misconfigured automation from exhausting resources by
enforcing per-agent-type concurrency and hourly/daily caps.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


# ── Models ───────────────────────────────────────────────────────────


class QuotaConfig(BaseModel):
    """Configuration for a single agent type's quota."""

    agent_type: str
    max_concurrent: int = 10
    max_per_hour: int = 100
    max_per_day: int = 1000
    priority: int = 5  # 1 (highest) to 10 (lowest)


class QuotaUsage(BaseModel):
    """Current usage statistics for a single agent type."""

    agent_type: str
    active_count: int = 0
    hourly_count: int = 0
    daily_count: int = 0
    peak_concurrent: int = 0
    rejected_count: int = 0
    total_acquired: int = 0
    total_released: int = 0


class QuotaCheckResult(BaseModel):
    """Result of checking whether an agent execution is allowed."""

    allowed: bool
    reason: str = ""
    wait_seconds: float = 0.0
    current_usage: QuotaUsage | None = None


# ── Default quotas ───────────────────────────────────────────────────

DEFAULT_QUOTAS: dict[str, QuotaConfig] = {
    "investigation": QuotaConfig(
        agent_type="investigation",
        max_concurrent=10,
        max_per_hour=100,
        max_per_day=1000,
    ),
    "remediation": QuotaConfig(
        agent_type="remediation",
        max_concurrent=5,
        max_per_hour=50,
        max_per_day=500,
    ),
    "security": QuotaConfig(
        agent_type="security",
        max_concurrent=5,
        max_per_hour=50,
        max_per_day=500,
    ),
    "cost": QuotaConfig(
        agent_type="cost",
        max_concurrent=3,
        max_per_hour=30,
        max_per_day=300,
    ),
    "learning": QuotaConfig(
        agent_type="learning",
        max_concurrent=2,
        max_per_hour=20,
        max_per_day=200,
    ),
    "prediction": QuotaConfig(
        agent_type="prediction",
        max_concurrent=3,
        max_per_hour=30,
        max_per_day=300,
    ),
    "supervisor": QuotaConfig(
        agent_type="supervisor",
        max_concurrent=2,
        max_per_hour=20,
        max_per_day=200,
    ),
}


# ── Manager ──────────────────────────────────────────────────────────


class ResourceQuotaManager:
    """Semaphore-style gate for agent execution with quotas.

    Parameters
    ----------
    global_max_concurrent:
        Hard cap on total concurrent agent executions across all types.
    enabled:
        When ``False``, all quota checks return allowed=True.
    """

    def __init__(
        self,
        global_max_concurrent: int = 20,
        enabled: bool = True,
    ) -> None:
        self._enabled = enabled
        self._global_max = global_max_concurrent
        self._quotas: dict[str, QuotaConfig] = dict(DEFAULT_QUOTAS)
        self._usage: dict[str, QuotaUsage] = {}
        self._active_executions: dict[str, str] = {}  # exec_id → agent_type
        # Rolling window tracking
        self._hourly_timestamps: dict[str, list[float]] = {}
        self._daily_timestamps: dict[str, list[float]] = {}

    def _ensure_usage(self, agent_type: str) -> QuotaUsage:
        if agent_type not in self._usage:
            self._usage[agent_type] = QuotaUsage(agent_type=agent_type)
        return self._usage[agent_type]

    def _ensure_quota(self, agent_type: str) -> QuotaConfig:
        if agent_type not in self._quotas:
            self._quotas[agent_type] = QuotaConfig(agent_type=agent_type)
        return self._quotas[agent_type]

    # ── Configuration ────────────────────────────────────────────

    def set_quota(self, config: QuotaConfig) -> QuotaConfig:
        self._quotas[config.agent_type] = config
        logger.info("quota_configured", agent_type=config.agent_type)
        return config

    def get_quota(self, agent_type: str) -> QuotaConfig | None:
        return self._quotas.get(agent_type)

    def list_quotas(self) -> list[QuotaConfig]:
        return list(self._quotas.values())

    # ── Acquire / Release ────────────────────────────────────────

    def check(self, agent_type: str) -> QuotaCheckResult:
        """Check if an agent execution is allowed without acquiring."""
        if not self._enabled:
            return QuotaCheckResult(allowed=True, reason="quotas_disabled")

        quota = self._ensure_quota(agent_type)
        usage = self._ensure_usage(agent_type)
        self._prune_timestamps(agent_type)

        # Global concurrent limit
        total_active = len(self._active_executions)
        if total_active >= self._global_max:
            return QuotaCheckResult(
                allowed=False,
                reason=f"global_concurrent_limit_{self._global_max}",
                current_usage=usage,
            )

        # Per-type concurrent limit
        if usage.active_count >= quota.max_concurrent:
            return QuotaCheckResult(
                allowed=False,
                reason=f"concurrent_limit_{quota.max_concurrent}",
                current_usage=usage,
            )

        # Hourly limit
        hourly = len(self._hourly_timestamps.get(agent_type, []))
        if hourly >= quota.max_per_hour:
            return QuotaCheckResult(
                allowed=False,
                reason=f"hourly_limit_{quota.max_per_hour}",
                current_usage=usage,
            )

        # Daily limit
        daily = len(self._daily_timestamps.get(agent_type, []))
        if daily >= quota.max_per_day:
            return QuotaCheckResult(
                allowed=False,
                reason=f"daily_limit_{quota.max_per_day}",
                current_usage=usage,
            )

        return QuotaCheckResult(allowed=True, reason="allowed", current_usage=usage)

    def acquire(self, agent_type: str, execution_id: str) -> QuotaCheckResult:
        """Attempt to acquire a slot for the given agent execution."""
        result = self.check(agent_type)
        if not result.allowed:
            usage = self._ensure_usage(agent_type)
            usage.rejected_count += 1
            return result

        now = time.time()
        usage = self._ensure_usage(agent_type)
        usage.active_count += 1
        usage.total_acquired += 1
        if usage.active_count > usage.peak_concurrent:
            usage.peak_concurrent = usage.active_count

        self._active_executions[execution_id] = agent_type

        # Record timestamp for hourly/daily tracking
        self._hourly_timestamps.setdefault(agent_type, []).append(now)
        self._daily_timestamps.setdefault(agent_type, []).append(now)

        # Update usage counts
        self._prune_timestamps(agent_type)
        usage.hourly_count = len(self._hourly_timestamps.get(agent_type, []))
        usage.daily_count = len(self._daily_timestamps.get(agent_type, []))

        return QuotaCheckResult(allowed=True, reason="acquired", current_usage=usage)

    def release(self, execution_id: str) -> bool:
        """Release a previously acquired slot."""
        agent_type = self._active_executions.pop(execution_id, None)
        if agent_type is None:
            return False
        usage = self._ensure_usage(agent_type)
        usage.active_count = max(0, usage.active_count - 1)
        usage.total_released += 1
        return True

    def _prune_timestamps(self, agent_type: str) -> None:
        """Remove timestamps outside the rolling window."""
        now = time.time()
        hour_ago = now - 3600
        day_ago = now - 86400
        if agent_type in self._hourly_timestamps:
            self._hourly_timestamps[agent_type] = [
                ts for ts in self._hourly_timestamps[agent_type] if ts > hour_ago
            ]
        if agent_type in self._daily_timestamps:
            self._daily_timestamps[agent_type] = [
                ts for ts in self._daily_timestamps[agent_type] if ts > day_ago
            ]

    # ── Stats ────────────────────────────────────────────────────

    def get_usage(self, agent_type: str) -> QuotaUsage:
        self._prune_timestamps(agent_type)
        usage = self._ensure_usage(agent_type)
        usage.hourly_count = len(self._hourly_timestamps.get(agent_type, []))
        usage.daily_count = len(self._daily_timestamps.get(agent_type, []))
        return usage

    def get_all_usage(self) -> list[QuotaUsage]:
        return [self.get_usage(at) for at in self._quotas]

    def get_stats(self) -> dict[str, Any]:
        total_active = len(self._active_executions)
        total_rejected = sum(u.rejected_count for u in self._usage.values())
        return {
            "enabled": self._enabled,
            "global_max_concurrent": self._global_max,
            "total_active": total_active,
            "total_rejected": total_rejected,
            "agent_types": len(self._quotas),
        }

    def reset(self, agent_type: str | None = None) -> None:
        """Reset usage counters. If *agent_type* is None, reset all."""
        if agent_type:
            self._usage.pop(agent_type, None)
            self._hourly_timestamps.pop(agent_type, None)
            self._daily_timestamps.pop(agent_type, None)
        else:
            self._usage.clear()
            self._hourly_timestamps.clear()
            self._daily_timestamps.clear()
            self._active_executions.clear()
