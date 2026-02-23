"""Tests for the feature flag manager with percentage rollout and targeting."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from shieldops.config.feature_flags import (
    FeatureFlag,
    FeatureFlagManager,
    FlagContext,
    FlagEvaluation,
    FlagStatus,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _make_manager(**kwargs: object) -> FeatureFlagManager:
    return FeatureFlagManager(**kwargs)


def _flag(name: str, **overrides: object) -> FeatureFlag:
    defaults = {"name": name, "status": FlagStatus.DISABLED}
    defaults.update(overrides)
    return FeatureFlag(**defaults)


# =========================================================================
# CRUD: register / get / delete / list
# =========================================================================


class TestCRUD:
    def test_register_returns_flag(self):
        mgr = _make_manager()
        flag = mgr.register(_flag("f1"))
        assert flag.name == "f1"

    def test_get_registered_flag(self):
        mgr = _make_manager()
        mgr.register(_flag("f1"))
        assert mgr.get("f1") is not None
        assert mgr.get("f1").name == "f1"

    def test_get_unregistered_returns_none(self):
        mgr = _make_manager()
        assert mgr.get("missing") is None

    def test_delete_existing_flag(self):
        mgr = _make_manager()
        mgr.register(_flag("f1"))
        assert mgr.delete("f1") is True
        assert mgr.get("f1") is None

    def test_delete_nonexistent_returns_false(self):
        mgr = _make_manager()
        assert mgr.delete("nope") is False

    def test_list_flags_empty(self):
        mgr = _make_manager()
        assert mgr.list_flags() == []

    def test_list_flags_returns_all(self):
        mgr = _make_manager()
        mgr.register(_flag("a"))
        mgr.register(_flag("b"))
        names = {f.name for f in mgr.list_flags()}
        assert names == {"a", "b"}

    def test_register_updates_existing(self):
        mgr = _make_manager()
        mgr.register(_flag("f", description="old"))
        mgr.register(_flag("f", description="new"))
        assert mgr.get("f").description == "new"

    def test_register_sets_updated_at(self):
        mgr = _make_manager()
        before = time.time()
        flag = mgr.register(_flag("f"))
        assert flag.updated_at >= before


# =========================================================================
# Evaluate ENABLED
# =========================================================================


class TestEvaluateEnabled:
    def test_enabled_returns_true(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.ENABLED))
        result = mgr.evaluate("f")
        assert result.enabled is True

    def test_enabled_reason(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.ENABLED))
        result = mgr.evaluate("f")
        assert result.reason == "enabled"

    def test_enabled_with_default_variant(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.ENABLED, default_variant="v1"))
        result = mgr.evaluate("f")
        assert result.variant == "v1"

    def test_enabled_picks_first_variant_if_no_default(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.ENABLED, variants={"alpha": {}, "beta": {}}))
        result = mgr.evaluate("f")
        assert result.variant in ("alpha", "beta")


# =========================================================================
# Evaluate DISABLED
# =========================================================================


class TestEvaluateDisabled:
    def test_disabled_returns_false(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.DISABLED))
        result = mgr.evaluate("f")
        assert result.enabled is False

    def test_disabled_reason(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.DISABLED))
        result = mgr.evaluate("f")
        assert result.reason == "disabled"

    def test_disabled_empty_variant(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.DISABLED))
        result = mgr.evaluate("f")
        assert result.variant == ""


# =========================================================================
# Evaluate PERCENTAGE
# =========================================================================


class TestEvaluatePercentage:
    def test_deterministic_same_user(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.PERCENTAGE, rollout_percentage=50.0))
        ctx = FlagContext(user_id="user-abc")

        r1 = mgr.evaluate("f", ctx)
        r2 = mgr.evaluate("f", ctx)
        assert r1.enabled == r2.enabled

    def test_100_percent_always_enabled(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.PERCENTAGE, rollout_percentage=100.0))
        ctx = FlagContext(user_id="any-user")
        result = mgr.evaluate("f", ctx)
        assert result.enabled is True

    def test_0_percent_always_disabled(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.PERCENTAGE, rollout_percentage=0.0))
        ctx = FlagContext(user_id="any-user")
        result = mgr.evaluate("f", ctx)
        assert result.enabled is False

    def test_no_entity_returns_false(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.PERCENTAGE, rollout_percentage=50.0))
        ctx = FlagContext()
        result = mgr.evaluate("f", ctx)
        assert result.enabled is False
        assert "no_entity" in result.reason

    def test_percentage_uses_org_id_fallback(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.PERCENTAGE, rollout_percentage=100.0))
        ctx = FlagContext(org_id="org-1")
        result = mgr.evaluate("f", ctx)
        assert result.enabled is True

    def test_percentage_reason_contains_values(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.PERCENTAGE, rollout_percentage=50.0))
        ctx = FlagContext(user_id="u1")
        result = mgr.evaluate("f", ctx)
        assert "percentage_" in result.reason
        assert "_vs_50.0" in result.reason


# =========================================================================
# Evaluate TARGETED
# =========================================================================


class TestEvaluateTargeted:
    def test_org_id_match(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.TARGETED, target_org_ids=["org-1", "org-2"]))
        ctx = FlagContext(org_id="org-1")
        result = mgr.evaluate("f", ctx)
        assert result.enabled is True
        assert result.reason == "targeted_org"

    def test_user_id_match(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.TARGETED, target_user_ids=["u-1"]))
        ctx = FlagContext(user_id="u-1")
        result = mgr.evaluate("f", ctx)
        assert result.enabled is True
        assert result.reason == "targeted_user"

    def test_no_match(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.TARGETED, target_org_ids=["org-1"]))
        ctx = FlagContext(org_id="org-999")
        result = mgr.evaluate("f", ctx)
        assert result.enabled is False
        assert result.reason == "not_targeted"

    def test_empty_context_not_targeted(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.TARGETED, target_org_ids=["org-1"]))
        result = mgr.evaluate("f", FlagContext())
        assert result.enabled is False

    def test_targeted_returns_default_variant(self):
        mgr = _make_manager()
        mgr.register(
            _flag(
                "f",
                status=FlagStatus.TARGETED,
                target_user_ids=["u-1"],
                default_variant="beta",
            )
        )
        ctx = FlagContext(user_id="u-1")
        result = mgr.evaluate("f", ctx)
        assert result.variant == "beta"


# =========================================================================
# Evaluate with no context
# =========================================================================


class TestEvaluateNoContext:
    def test_enabled_flag_no_context(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.ENABLED))
        result = mgr.evaluate("f")
        assert result.enabled is True

    def test_disabled_flag_no_context(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.DISABLED))
        result = mgr.evaluate("f")
        assert result.enabled is False

    def test_percentage_flag_no_context(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.PERCENTAGE, rollout_percentage=50.0))
        result = mgr.evaluate("f", None)
        assert result.enabled is False


# =========================================================================
# Flag not found
# =========================================================================


class TestFlagNotFound:
    def test_returns_false(self):
        mgr = _make_manager()
        result = mgr.evaluate("nonexistent")
        assert result.enabled is False

    def test_reason_is_flag_not_found(self):
        mgr = _make_manager()
        result = mgr.evaluate("nonexistent")
        assert result.reason == "flag_not_found"

    def test_flag_name_set(self):
        mgr = _make_manager()
        result = mgr.evaluate("nonexistent")
        assert result.flag_name == "nonexistent"


# =========================================================================
# Update partial fields
# =========================================================================


class TestUpdate:
    def test_update_description(self):
        mgr = _make_manager()
        mgr.register(_flag("f", description="old"))
        updated = mgr.update("f", {"description": "new"})
        assert updated is not None
        assert updated.description == "new"

    def test_update_status(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.DISABLED))
        updated = mgr.update("f", {"status": FlagStatus.ENABLED})
        assert updated.status == FlagStatus.ENABLED

    def test_update_nonexistent_returns_none(self):
        mgr = _make_manager()
        assert mgr.update("nope", {"description": "x"}) is None

    def test_update_ignores_name_field(self):
        mgr = _make_manager()
        mgr.register(_flag("f"))
        updated = mgr.update("f", {"name": "renamed"})
        assert updated.name == "f"

    def test_update_sets_updated_at(self):
        mgr = _make_manager()
        mgr.register(_flag("f"))
        before = time.time()
        mgr.update("f", {"description": "changed"})
        assert mgr.get("f").updated_at >= before


# =========================================================================
# Evaluation log tracking
# =========================================================================


class TestEvaluationLog:
    def test_log_grows_on_evaluate(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.ENABLED))
        mgr.evaluate("f")
        mgr.evaluate("f")
        stats = mgr.get_stats()
        assert stats["total_evaluations"] == 2

    def test_log_contains_flag_info(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.ENABLED))
        mgr.evaluate("f")
        assert mgr._evaluation_log[-1]["flag"] == "f"
        assert mgr._evaluation_log[-1]["enabled"] is True

    def test_log_bounded(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.ENABLED))
        for _ in range(10001):
            mgr.evaluate("f")
        assert len(mgr._evaluation_log) <= 10000


# =========================================================================
# sync_to_redis
# =========================================================================


class TestSyncToRedis:
    @pytest.mark.asyncio
    async def test_sync_pushes_all_flags(self):
        redis = AsyncMock()
        mgr = _make_manager(redis_cache=redis)
        mgr.register(_flag("f1", status=FlagStatus.ENABLED))
        mgr.register(_flag("f2", status=FlagStatus.DISABLED))

        count = await mgr.sync_to_redis()
        assert count == 2
        assert redis.set.await_count == 2

    @pytest.mark.asyncio
    async def test_sync_no_redis_returns_zero(self):
        mgr = _make_manager()
        count = await mgr.sync_to_redis()
        assert count == 0

    @pytest.mark.asyncio
    async def test_sync_updates_last_sync(self):
        redis = AsyncMock()
        mgr = _make_manager(redis_cache=redis)
        mgr.register(_flag("f"))

        before = time.time()
        await mgr.sync_to_redis()
        assert mgr._last_sync >= before

    @pytest.mark.asyncio
    async def test_sync_uses_correct_namespace(self):
        redis = AsyncMock()
        mgr = _make_manager(redis_cache=redis)
        mgr.register(_flag("myflag"))

        await mgr.sync_to_redis()
        call_kwargs = redis.set.call_args_list[0]
        # namespace keyword arg
        assert (
            call_kwargs.kwargs.get("namespace") == "feature_flags"
            or call_kwargs[1].get("namespace") == "feature_flags"
        )


# =========================================================================
# Stats by status
# =========================================================================


class TestGetStats:
    def test_empty_stats(self):
        mgr = _make_manager()
        stats = mgr.get_stats()
        assert stats["total_flags"] == 0
        assert stats["by_status"] == {}

    def test_counts_by_status(self):
        mgr = _make_manager()
        mgr.register(_flag("a", status=FlagStatus.ENABLED))
        mgr.register(_flag("b", status=FlagStatus.ENABLED))
        mgr.register(_flag("c", status=FlagStatus.DISABLED))

        stats = mgr.get_stats()
        assert stats["total_flags"] == 3
        assert stats["by_status"]["enabled"] == 2
        assert stats["by_status"]["disabled"] == 1

    def test_last_sync_tracked(self):
        mgr = _make_manager()
        stats = mgr.get_stats()
        assert stats["last_sync"] == 0.0


# =========================================================================
# Variants and default_variant
# =========================================================================


class TestVariants:
    def test_default_variant_on_enabled(self):
        mgr = _make_manager()
        mgr.register(
            _flag(
                "f",
                status=FlagStatus.ENABLED,
                default_variant="v2",
                variants={"v1": {"color": "red"}, "v2": {"color": "blue"}},
            )
        )
        result = mgr.evaluate("f")
        assert result.variant == "v2"

    def test_no_variant_on_disabled(self):
        mgr = _make_manager()
        mgr.register(_flag("f", status=FlagStatus.DISABLED, default_variant="v1"))
        result = mgr.evaluate("f")
        assert result.variant == ""


# =========================================================================
# evaluate_all
# =========================================================================


class TestEvaluateAll:
    def test_evaluates_all_flags(self):
        mgr = _make_manager()
        mgr.register(_flag("a", status=FlagStatus.ENABLED))
        mgr.register(_flag("b", status=FlagStatus.DISABLED))

        results = mgr.evaluate_all()
        assert len(results) == 2
        names = {r.flag_name for r in results}
        assert names == {"a", "b"}

    def test_passes_context_to_all(self):
        mgr = _make_manager()
        mgr.register(_flag("a", status=FlagStatus.TARGETED, target_user_ids=["u1"]))
        mgr.register(_flag("b", status=FlagStatus.TARGETED, target_user_ids=["u2"]))

        ctx = FlagContext(user_id="u1")
        results = mgr.evaluate_all(ctx)
        by_name = {r.flag_name: r for r in results}
        assert by_name["a"].enabled is True
        assert by_name["b"].enabled is False


# =========================================================================
# Model tests
# =========================================================================


class TestModels:
    def test_feature_flag_defaults(self):
        f = FeatureFlag(name="test")
        assert f.status == FlagStatus.DISABLED
        assert f.rollout_percentage == 0.0
        assert f.target_org_ids == []
        assert f.target_user_ids == []
        assert f.variants == {}
        assert f.default_variant == ""

    def test_flag_evaluation_model(self):
        e = FlagEvaluation(flag_name="f", enabled=True, reason="test")
        assert e.flag_name == "f"
        assert e.enabled is True
        assert e.variant == ""

    def test_flag_context_defaults(self):
        ctx = FlagContext()
        assert ctx.user_id == ""
        assert ctx.org_id == ""
        assert ctx.environment == ""
        assert ctx.attributes == {}

    def test_flag_status_values(self):
        assert FlagStatus.ENABLED == "enabled"
        assert FlagStatus.DISABLED == "disabled"
        assert FlagStatus.PERCENTAGE == "percentage"
        assert FlagStatus.TARGETED == "targeted"
