"""Comprehensive tests for the ResourceQuotaManager.

Covers:
- Default quotas for all agent types
- acquire / release lifecycle
- Concurrent limit enforcement
- Hourly limit enforcement
- Daily limit enforcement
- Global max concurrent enforcement
- check() without acquiring
- rejected_count tracking
- peak_concurrent tracking
- release unknown execution_id returns False
- Disabled mode always allows
- set_quota / get_quota / list_quotas
- get_usage / get_all_usage
- reset() clears counters
- Stats overview
"""

from __future__ import annotations

import time

from shieldops.agents.resource_quotas import (
    QuotaConfig,
    ResourceQuotaManager,
)

# =========================================================================
# Default quotas
# =========================================================================


class TestDefaultQuotas:
    """Default quota configurations for known agent types."""

    def test_default_quotas_present(self) -> None:
        mgr = ResourceQuotaManager()
        quotas = {q.agent_type for q in mgr.list_quotas()}
        expected = {
            "investigation",
            "remediation",
            "security",
            "cost",
            "learning",
            "prediction",
            "supervisor",
        }
        assert expected.issubset(quotas)

    def test_investigation_default_concurrent(self) -> None:
        mgr = ResourceQuotaManager()
        q = mgr.get_quota("investigation")
        assert q is not None
        assert q.max_concurrent == 10

    def test_remediation_default_concurrent(self) -> None:
        mgr = ResourceQuotaManager()
        q = mgr.get_quota("remediation")
        assert q is not None
        assert q.max_concurrent == 5

    def test_learning_default_concurrent(self) -> None:
        mgr = ResourceQuotaManager()
        q = mgr.get_quota("learning")
        assert q is not None
        assert q.max_concurrent == 2


# =========================================================================
# Acquire / Release lifecycle
# =========================================================================


class TestAcquireRelease:
    """Basic acquire and release slot."""

    def test_acquire_succeeds(self) -> None:
        mgr = ResourceQuotaManager()
        result = mgr.acquire("investigation", "exec-1")
        assert result.allowed is True
        assert result.reason == "acquired"

    def test_release_succeeds(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        assert mgr.release("exec-1") is True

    def test_release_decrements_active(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        mgr.release("exec-1")
        usage = mgr.get_usage("investigation")
        assert usage.active_count == 0

    def test_acquire_increments_active(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        usage = mgr.get_usage("investigation")
        assert usage.active_count == 1

    def test_acquire_and_release_multiple(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        mgr.acquire("investigation", "exec-2")
        assert mgr.get_usage("investigation").active_count == 2
        mgr.release("exec-1")
        assert mgr.get_usage("investigation").active_count == 1
        mgr.release("exec-2")
        assert mgr.get_usage("investigation").active_count == 0


# =========================================================================
# Concurrent limit enforcement
# =========================================================================


class TestConcurrentLimit:
    """Per-type max_concurrent enforcement."""

    def test_exceeds_concurrent_limit(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.set_quota(
            QuotaConfig(
                agent_type="test",
                max_concurrent=2,
                max_per_hour=1000,
                max_per_day=10000,
            )
        )
        mgr.acquire("test", "exec-1")
        mgr.acquire("test", "exec-2")
        result = mgr.acquire("test", "exec-3")
        assert result.allowed is False
        assert "concurrent_limit" in result.reason

    def test_under_concurrent_limit(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.set_quota(
            QuotaConfig(
                agent_type="test",
                max_concurrent=3,
                max_per_hour=1000,
                max_per_day=10000,
            )
        )
        mgr.acquire("test", "exec-1")
        mgr.acquire("test", "exec-2")
        result = mgr.acquire("test", "exec-3")
        assert result.allowed is True

    def test_release_frees_slot(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.set_quota(
            QuotaConfig(
                agent_type="test",
                max_concurrent=1,
                max_per_hour=1000,
                max_per_day=10000,
            )
        )
        mgr.acquire("test", "exec-1")
        assert mgr.acquire("test", "exec-2").allowed is False
        mgr.release("exec-1")
        assert mgr.acquire("test", "exec-2").allowed is True


# =========================================================================
# Hourly limit enforcement
# =========================================================================


class TestHourlyLimit:
    """max_per_hour enforcement using rolling window."""

    def test_exceeds_hourly_limit(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.set_quota(
            QuotaConfig(
                agent_type="test",
                max_concurrent=100,
                max_per_hour=3,
                max_per_day=10000,
            )
        )
        mgr.acquire("test", "exec-1")
        mgr.release("exec-1")
        mgr.acquire("test", "exec-2")
        mgr.release("exec-2")
        mgr.acquire("test", "exec-3")
        mgr.release("exec-3")
        result = mgr.acquire("test", "exec-4")
        assert result.allowed is False
        assert "hourly_limit" in result.reason

    def test_hourly_window_expires(self) -> None:
        """Timestamps older than 1 hour are pruned."""
        mgr = ResourceQuotaManager()
        mgr.set_quota(
            QuotaConfig(agent_type="test", max_concurrent=100, max_per_hour=1, max_per_day=10000)
        )
        # Inject an old timestamp (more than 1 hour ago)
        old_time = time.time() - 3700
        mgr._hourly_timestamps.setdefault("test", []).append(old_time)
        mgr._daily_timestamps.setdefault("test", []).append(old_time)
        result = mgr.acquire("test", "exec-1")
        assert result.allowed is True


# =========================================================================
# Daily limit enforcement
# =========================================================================


class TestDailyLimit:
    """max_per_day enforcement."""

    def test_exceeds_daily_limit(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.set_quota(
            QuotaConfig(agent_type="test", max_concurrent=100, max_per_hour=100, max_per_day=2)
        )
        mgr.acquire("test", "exec-1")
        mgr.release("exec-1")
        mgr.acquire("test", "exec-2")
        mgr.release("exec-2")
        result = mgr.acquire("test", "exec-3")
        assert result.allowed is False
        assert "daily_limit" in result.reason


# =========================================================================
# Global max concurrent
# =========================================================================


class TestGlobalMaxConcurrent:
    """global_max_concurrent caps total active across all types."""

    def test_exceeds_global_max(self) -> None:
        mgr = ResourceQuotaManager(global_max_concurrent=2)
        mgr.acquire("investigation", "exec-1")
        mgr.acquire("remediation", "exec-2")
        result = mgr.acquire("security", "exec-3")
        assert result.allowed is False
        assert "global_concurrent_limit" in result.reason

    def test_under_global_max(self) -> None:
        mgr = ResourceQuotaManager(global_max_concurrent=5)
        mgr.acquire("investigation", "exec-1")
        mgr.acquire("remediation", "exec-2")
        result = mgr.acquire("security", "exec-3")
        assert result.allowed is True


# =========================================================================
# check() without acquiring
# =========================================================================


class TestCheck:
    """check() reports allowed/denied without modifying state."""

    def test_check_allowed(self) -> None:
        mgr = ResourceQuotaManager()
        result = mgr.check("investigation")
        assert result.allowed is True

    def test_check_does_not_acquire(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.check("investigation")
        usage = mgr.get_usage("investigation")
        assert usage.active_count == 0

    def test_check_denied_concurrent(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.set_quota(
            QuotaConfig(
                agent_type="test",
                max_concurrent=1,
                max_per_hour=1000,
                max_per_day=10000,
            )
        )
        mgr.acquire("test", "exec-1")
        result = mgr.check("test")
        assert result.allowed is False

    def test_check_returns_current_usage(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        result = mgr.check("investigation")
        assert result.current_usage is not None
        assert result.current_usage.active_count == 1


# =========================================================================
# Rejected count tracking
# =========================================================================


class TestRejectedCount:
    """rejected_count increments on denied acquire()."""

    def test_rejected_count_increments(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.set_quota(
            QuotaConfig(
                agent_type="test",
                max_concurrent=1,
                max_per_hour=1000,
                max_per_day=10000,
            )
        )
        mgr.acquire("test", "exec-1")
        mgr.acquire("test", "exec-2")  # rejected
        mgr.acquire("test", "exec-3")  # rejected
        usage = mgr.get_usage("test")
        assert usage.rejected_count == 2

    def test_check_does_not_increment_rejected(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.set_quota(
            QuotaConfig(
                agent_type="test",
                max_concurrent=1,
                max_per_hour=1000,
                max_per_day=10000,
            )
        )
        mgr.acquire("test", "exec-1")
        mgr.check("test")  # check only, not acquire
        usage = mgr.get_usage("test")
        assert usage.rejected_count == 0


# =========================================================================
# Peak concurrent tracking
# =========================================================================


class TestPeakConcurrent:
    """peak_concurrent records the high-water mark."""

    def test_peak_concurrent_tracking(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        mgr.acquire("investigation", "exec-2")
        mgr.acquire("investigation", "exec-3")
        mgr.release("exec-1")
        mgr.release("exec-2")
        usage = mgr.get_usage("investigation")
        assert usage.peak_concurrent == 3

    def test_peak_concurrent_does_not_decrease(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        mgr.acquire("investigation", "exec-2")
        mgr.release("exec-1")
        mgr.release("exec-2")
        usage = mgr.get_usage("investigation")
        assert usage.peak_concurrent == 2


# =========================================================================
# Release unknown execution_id
# =========================================================================


class TestReleaseUnknown:
    """Release of an unknown execution_id returns False."""

    def test_release_unknown_returns_false(self) -> None:
        mgr = ResourceQuotaManager()
        assert mgr.release("unknown-id") is False

    def test_double_release_returns_false(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        assert mgr.release("exec-1") is True
        assert mgr.release("exec-1") is False


# =========================================================================
# Disabled mode
# =========================================================================


class TestDisabledMode:
    """enabled=False bypasses all quota checks."""

    def test_disabled_always_allows(self) -> None:
        mgr = ResourceQuotaManager(global_max_concurrent=0, enabled=False)
        result = mgr.check("investigation")
        assert result.allowed is True
        assert result.reason == "quotas_disabled"

    def test_disabled_acquire_returns_allowed(self) -> None:
        """acquire() calls check() internally; disabled skips enforcement."""
        mgr = ResourceQuotaManager(enabled=False)
        mgr.set_quota(
            QuotaConfig(agent_type="test", max_concurrent=0, max_per_hour=0, max_per_day=0)
        )
        result = mgr.acquire("test", "exec-1")
        # When disabled, check() returns allowed=True with reason "quotas_disabled",
        # but acquire only proceeds to record if check says allowed — let's verify
        assert result.allowed is True


# =========================================================================
# set_quota / get_quota / list_quotas
# =========================================================================


class TestQuotaConfiguration:
    """Quota CRUD operations."""

    def test_set_quota(self) -> None:
        mgr = ResourceQuotaManager()
        config = QuotaConfig(agent_type="custom", max_concurrent=99)
        mgr.set_quota(config)
        assert mgr.get_quota("custom") is not None
        assert mgr.get_quota("custom").max_concurrent == 99

    def test_get_quota_missing(self) -> None:
        mgr = ResourceQuotaManager()
        assert mgr.get_quota("nonexistent") is None

    def test_list_quotas(self) -> None:
        mgr = ResourceQuotaManager()
        quotas = mgr.list_quotas()
        assert len(quotas) >= 7  # default quotas

    def test_set_quota_overwrites(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.set_quota(QuotaConfig(agent_type="investigation", max_concurrent=99))
        assert mgr.get_quota("investigation").max_concurrent == 99


# =========================================================================
# get_usage / get_all_usage
# =========================================================================


class TestUsage:
    """Usage reporting."""

    def test_get_usage_new_type(self) -> None:
        mgr = ResourceQuotaManager()
        usage = mgr.get_usage("investigation")
        assert usage.active_count == 0
        assert usage.hourly_count == 0
        assert usage.daily_count == 0

    def test_get_usage_after_acquire(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        usage = mgr.get_usage("investigation")
        assert usage.active_count == 1
        assert usage.total_acquired == 1

    def test_get_all_usage(self) -> None:
        mgr = ResourceQuotaManager()
        all_usage = mgr.get_all_usage()
        # Should have one entry per default quota type
        assert len(all_usage) >= 7

    def test_get_usage_tracks_hourly_daily(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        usage = mgr.get_usage("investigation")
        assert usage.hourly_count >= 1
        assert usage.daily_count >= 1


# =========================================================================
# reset()
# =========================================================================


class TestReset:
    """reset() clears counters."""

    def test_reset_specific_agent_type(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        mgr.reset("investigation")
        usage = mgr.get_usage("investigation")
        assert usage.active_count == 0
        assert usage.hourly_count == 0

    def test_reset_all(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        mgr.acquire("remediation", "exec-2")
        mgr.reset()
        usage_inv = mgr.get_usage("investigation")
        usage_rem = mgr.get_usage("remediation")
        assert usage_inv.active_count == 0
        assert usage_rem.active_count == 0

    def test_reset_clears_active_executions(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        mgr.reset()
        # After full reset, release of previously acquired id should return False
        assert mgr.release("exec-1") is False


# =========================================================================
# Stats overview
# =========================================================================


class TestStats:
    """get_stats() summary data."""

    def test_stats_initial(self) -> None:
        mgr = ResourceQuotaManager()
        stats = mgr.get_stats()
        assert stats["enabled"] is True
        assert stats["total_active"] == 0
        assert stats["total_rejected"] == 0
        assert stats["agent_types"] >= 7

    def test_stats_after_activity(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.acquire("investigation", "exec-1")
        stats = mgr.get_stats()
        assert stats["total_active"] == 1

    def test_stats_tracks_rejected(self) -> None:
        mgr = ResourceQuotaManager()
        mgr.set_quota(
            QuotaConfig(agent_type="test", max_concurrent=0, max_per_hour=0, max_per_day=0)
        )
        mgr.acquire("test", "exec-1")
        stats = mgr.get_stats()
        assert stats["total_rejected"] >= 1

    def test_stats_global_max(self) -> None:
        mgr = ResourceQuotaManager(global_max_concurrent=42)
        stats = mgr.get_stats()
        assert stats["global_max_concurrent"] == 42
