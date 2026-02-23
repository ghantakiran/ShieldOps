"""Feature flag management with percentage rollout and targeting.

Supports flag lifecycle (enabled / disabled / percentage / targeted),
deterministic hashing for stable rollout, and optional Redis sync.
"""

from __future__ import annotations

import enum
import hashlib
import time
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class FlagStatus(enum.StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    PERCENTAGE = "percentage"
    TARGETED = "targeted"


# ── Models ───────────────────────────────────────────────────────────


class FeatureFlag(BaseModel):
    """Definition of a single feature flag."""

    name: str
    description: str = ""
    status: FlagStatus = FlagStatus.DISABLED
    rollout_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    target_org_ids: list[str] = Field(default_factory=list)
    target_user_ids: list[str] = Field(default_factory=list)
    variants: dict[str, Any] = Field(default_factory=dict)
    default_variant: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    tags: list[str] = Field(default_factory=list)


class FlagEvaluation(BaseModel):
    """Result of evaluating a feature flag for a context."""

    flag_name: str
    enabled: bool
    variant: str = ""
    reason: str = ""


class FlagContext(BaseModel):
    """Context passed when evaluating a flag."""

    user_id: str = ""
    org_id: str = ""
    environment: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)


# ── Manager ──────────────────────────────────────────────────────────


class FeatureFlagManager:
    """Register, evaluate, and manage feature flags.

    Parameters
    ----------
    redis_cache:
        Optional Redis cache for cross-instance sync.
    sync_interval_seconds:
        How often to sync flags to/from Redis.
    """

    def __init__(
        self,
        redis_cache: Any = None,
        sync_interval_seconds: int = 30,
    ) -> None:
        self._flags: dict[str, FeatureFlag] = {}
        self._redis = redis_cache
        self._sync_interval = sync_interval_seconds
        self._last_sync: float = 0.0
        self._evaluation_log: list[dict[str, Any]] = []

    # ── CRUD ─────────────────────────────────────────────────────

    def register(self, flag: FeatureFlag) -> FeatureFlag:
        """Register or update a feature flag."""
        flag.updated_at = time.time()
        self._flags[flag.name] = flag
        logger.info("feature_flag_registered", name=flag.name, status=flag.status)
        return flag

    def get(self, name: str) -> FeatureFlag | None:
        return self._flags.get(name)

    def delete(self, name: str) -> bool:
        removed = self._flags.pop(name, None) is not None
        if removed:
            logger.info("feature_flag_deleted", name=name)
        return removed

    def list_flags(self) -> list[FeatureFlag]:
        return list(self._flags.values())

    def update(self, name: str, updates: dict[str, Any]) -> FeatureFlag | None:
        """Partial update of an existing flag."""
        flag = self._flags.get(name)
        if flag is None:
            return None
        for k, v in updates.items():
            if hasattr(flag, k) and k != "name":
                setattr(flag, k, v)
        flag.updated_at = time.time()
        self._flags[name] = flag
        return flag

    # ── Evaluation ───────────────────────────────────────────────

    @staticmethod
    def _hash_percent(flag_name: str, entity_id: str) -> float:
        """Deterministic hash → 0..100 for stable rollout."""
        digest = hashlib.md5(  # noqa: S324
            f"{flag_name}:{entity_id}".encode(),
            usedforsecurity=False,
        ).hexdigest()
        return int(digest[:8], 16) % 10000 / 100.0

    def evaluate(self, name: str, context: FlagContext | None = None) -> FlagEvaluation:
        """Evaluate a flag for the given context."""
        flag = self._flags.get(name)
        if flag is None:
            return FlagEvaluation(flag_name=name, enabled=False, reason="flag_not_found")

        ctx = context or FlagContext()

        # Fully enabled
        if flag.status == FlagStatus.ENABLED:
            variant = flag.default_variant or (next(iter(flag.variants)) if flag.variants else "")
            return self._eval_result(name, True, variant, "enabled")

        # Fully disabled
        if flag.status == FlagStatus.DISABLED:
            return self._eval_result(name, False, "", "disabled")

        # Targeted rollout (org/user whitelist)
        if flag.status == FlagStatus.TARGETED:
            if ctx.org_id and ctx.org_id in flag.target_org_ids:
                return self._eval_result(name, True, flag.default_variant, "targeted_org")
            if ctx.user_id and ctx.user_id in flag.target_user_ids:
                return self._eval_result(name, True, flag.default_variant, "targeted_user")
            return self._eval_result(name, False, "", "not_targeted")

        # Percentage rollout (deterministic hash on user_id or org_id)
        if flag.status == FlagStatus.PERCENTAGE:
            entity = ctx.user_id or ctx.org_id or ""
            if not entity:
                return self._eval_result(name, False, "", "no_entity_for_percentage")
            pct = self._hash_percent(name, entity)
            enabled = pct < flag.rollout_percentage
            reason = f"percentage_{pct:.2f}_vs_{flag.rollout_percentage}"
            variant = flag.default_variant if enabled else ""
            return self._eval_result(name, enabled, variant, reason)

        return self._eval_result(name, False, "", "unknown_status")

    def _eval_result(self, name: str, enabled: bool, variant: str, reason: str) -> FlagEvaluation:
        result = FlagEvaluation(flag_name=name, enabled=enabled, variant=variant, reason=reason)
        self._evaluation_log.append(
            {"flag": name, "enabled": enabled, "reason": reason, "ts": time.time()}
        )
        # Keep log bounded
        if len(self._evaluation_log) > 10000:
            self._evaluation_log = self._evaluation_log[-5000:]
        return result

    def evaluate_all(self, context: FlagContext | None = None) -> list[FlagEvaluation]:
        """Evaluate all registered flags for a context."""
        return [self.evaluate(name, context) for name in self._flags]

    # ── Sync ─────────────────────────────────────────────────────

    async def sync_to_redis(self) -> int:
        """Push all flags to Redis for cross-instance sharing."""
        if self._redis is None:
            return 0
        count = 0
        for flag in self._flags.values():
            await self._redis.set(
                f"ff:{flag.name}",
                flag.model_dump(),
                ttl=self._sync_interval * 3,
                namespace="feature_flags",
            )
            count += 1
        self._last_sync = time.time()
        return count

    async def sync_from_redis(self) -> int:
        """Pull flags from Redis (merge with local)."""
        if self._redis is None:
            return 0
        # Not implemented without scan — placeholder
        return 0

    # ── Stats ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for flag in self._flags.values():
            by_status[flag.status.value] = by_status.get(flag.status.value, 0) + 1
        return {
            "total_flags": len(self._flags),
            "by_status": by_status,
            "total_evaluations": len(self._evaluation_log),
            "last_sync": self._last_sync,
        }
