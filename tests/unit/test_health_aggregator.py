"""Tests for the health check aggregator with weighted scoring and trend detection."""

from __future__ import annotations

import time

import pytest

from shieldops.observability.health_aggregator import (
    AggregateHealth,
    ComponentHealth,
    HealthAggregator,
    HealthSnapshot,
    HealthStatus,
    HealthTrend,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _make_agg(**kwargs: object) -> HealthAggregator:
    return HealthAggregator(**kwargs)


# =========================================================================
# Register / unregister components
# =========================================================================


class TestRegistration:
    def test_register_returns_component(self):
        agg = _make_agg()
        comp = agg.register("db")
        assert comp.name == "db"
        assert comp.status == HealthStatus.UNKNOWN

    def test_register_with_weight(self):
        agg = _make_agg()
        comp = agg.register("db", weight=3.0)
        assert comp.weight == 3.0

    def test_register_critical(self):
        agg = _make_agg()
        comp = agg.register("db", is_critical=True)
        assert comp.is_critical is True

    def test_get_component(self):
        agg = _make_agg()
        agg.register("db")
        assert agg.get_component("db") is not None
        assert agg.get_component("db").name == "db"

    def test_get_unregistered_returns_none(self):
        agg = _make_agg()
        assert agg.get_component("missing") is None

    def test_unregister_existing(self):
        agg = _make_agg()
        agg.register("db")
        assert agg.unregister("db") is True
        assert agg.get_component("db") is None

    def test_unregister_nonexistent(self):
        agg = _make_agg()
        assert agg.unregister("nope") is False

    def test_list_components(self):
        agg = _make_agg()
        agg.register("a")
        agg.register("b")
        names = {c.name for c in agg.list_components()}
        assert names == {"a", "b"}

    def test_list_components_empty(self):
        agg = _make_agg()
        assert agg.list_components() == []


# =========================================================================
# compute() with all healthy
# =========================================================================


class TestAllHealthy:
    def test_score_is_100(self):
        agg = _make_agg()
        agg.register("db")
        agg.register("cache")
        agg.update_component("db", HealthStatus.HEALTHY)
        agg.update_component("cache", HealthStatus.HEALTHY)

        result = agg.compute()
        assert result.health_score == 100.0

    def test_status_is_healthy(self):
        agg = _make_agg()
        agg.register("db")
        agg.update_component("db", HealthStatus.HEALTHY)

        result = agg.compute()
        assert result.overall_status == HealthStatus.HEALTHY

    def test_components_included(self):
        agg = _make_agg()
        agg.register("db")
        agg.update_component("db", HealthStatus.HEALTHY)

        result = agg.compute()
        assert len(result.components) == 1
        assert result.components[0].name == "db"


# =========================================================================
# compute() with mixed statuses -> weighted score
# =========================================================================


class TestMixedHealth:
    def test_weighted_score(self):
        agg = _make_agg()
        agg.register("db", weight=2.0)
        agg.register("cache", weight=1.0)
        agg.update_component("db", HealthStatus.HEALTHY)  # 1.0 * 2.0
        agg.update_component("cache", HealthStatus.DEGRADED)  # 0.5 * 1.0

        result = agg.compute()
        # (2.0*1.0 + 1.0*0.5) / 3.0 * 100 = 83.33
        assert result.health_score == pytest.approx(83.33, abs=0.01)

    def test_all_degraded_score(self):
        agg = _make_agg()
        agg.register("a", weight=1.0)
        agg.register("b", weight=1.0)
        agg.update_component("a", HealthStatus.DEGRADED)
        agg.update_component("b", HealthStatus.DEGRADED)

        result = agg.compute()
        assert result.health_score == 50.0

    def test_unhealthy_component_lowers_score(self):
        agg = _make_agg()
        agg.register("a")
        agg.register("b")
        agg.update_component("a", HealthStatus.HEALTHY)
        agg.update_component("b", HealthStatus.UNHEALTHY)

        result = agg.compute()
        # (1.0 + 0.1) / 2 * 100 = 55.0
        assert result.health_score == 55.0


# =========================================================================
# Critical component forces status to CRITICAL
# =========================================================================


class TestCriticalComponent:
    def test_critical_component_critical_status_forces_overall_critical(self):
        agg = _make_agg()
        agg.register("db", is_critical=True)
        agg.register("cache")
        agg.update_component("db", HealthStatus.CRITICAL)
        agg.update_component("cache", HealthStatus.HEALTHY)

        result = agg.compute()
        assert result.overall_status == HealthStatus.CRITICAL
        assert result.health_score == 0.0

    def test_critical_unhealthy_forces_at_least_degraded(self):
        agg = _make_agg()
        agg.register("db", is_critical=True, weight=1.0)
        agg.register("cache", weight=10.0)
        agg.update_component("db", HealthStatus.UNHEALTHY)  # 0.1
        agg.update_component("cache", HealthStatus.HEALTHY)  # 1.0

        result = agg.compute()
        # Score = (1*0.1 + 10*1.0) / 11 * 100 = 91.82 -> normally HEALTHY
        # But critical component is unhealthy -> forced to DEGRADED
        assert result.overall_status == HealthStatus.DEGRADED

    def test_non_critical_unhealthy_no_override(self):
        agg = _make_agg()
        agg.register("db", is_critical=False, weight=1.0)
        agg.register("cache", weight=10.0)
        agg.update_component("db", HealthStatus.UNHEALTHY)
        agg.update_component("cache", HealthStatus.HEALTHY)

        result = agg.compute()
        # Score > degraded threshold, no critical override -> HEALTHY
        assert result.overall_status == HealthStatus.HEALTHY


# =========================================================================
# Threshold-based status
# =========================================================================


class TestThresholds:
    def test_below_degraded_threshold(self):
        agg = _make_agg(degraded_threshold=70.0, unhealthy_threshold=40.0)
        agg.register("a")
        agg.register("b")
        agg.update_component("a", HealthStatus.HEALTHY)  # 1.0
        agg.update_component("b", HealthStatus.DEGRADED)  # 0.5
        # Score = 75.0 -> >= degraded_threshold -> HEALTHY

        result = agg.compute()
        assert result.overall_status == HealthStatus.HEALTHY

    def test_exactly_at_degraded_threshold(self):
        agg = _make_agg(degraded_threshold=75.0, unhealthy_threshold=40.0)
        agg.register("a")
        agg.register("b")
        agg.update_component("a", HealthStatus.HEALTHY)
        agg.update_component("b", HealthStatus.DEGRADED)
        # Score = 75.0 -> >= 75.0 -> HEALTHY

        result = agg.compute()
        assert result.overall_status == HealthStatus.HEALTHY

    def test_below_unhealthy_threshold(self):
        agg = _make_agg(degraded_threshold=70.0, unhealthy_threshold=40.0)
        agg.register("a")
        agg.register("b")
        agg.update_component("a", HealthStatus.UNHEALTHY)  # 0.1
        agg.update_component("b", HealthStatus.UNHEALTHY)  # 0.1
        # Score = 10.0 -> < 40 -> UNHEALTHY

        result = agg.compute()
        assert result.overall_status == HealthStatus.UNHEALTHY

    def test_between_thresholds_is_degraded(self):
        agg = _make_agg(degraded_threshold=70.0, unhealthy_threshold=40.0)
        agg.register("a")
        agg.register("b")
        agg.update_component("a", HealthStatus.HEALTHY)  # 1.0
        agg.update_component("b", HealthStatus.UNHEALTHY)  # 0.1
        # Score = 55.0 -> between 40 and 70 -> DEGRADED

        result = agg.compute()
        assert result.overall_status == HealthStatus.DEGRADED

    def test_custom_thresholds(self):
        agg = _make_agg(degraded_threshold=90.0, unhealthy_threshold=60.0)
        agg.register("a")
        agg.update_component("a", HealthStatus.HEALTHY)
        result = agg.compute()
        assert result.health_score == 100.0
        assert result.overall_status == HealthStatus.HEALTHY


# =========================================================================
# Trend detection
# =========================================================================


class TestTrendDetection:
    def test_stable_with_few_snapshots(self):
        agg = _make_agg()
        agg.register("a")
        agg.update_component("a", HealthStatus.HEALTHY)
        result = agg.compute()
        assert result.trend == HealthTrend.STABLE

    def test_improving_trend(self):
        agg = _make_agg()
        agg.register("a")
        # Build history with low scores
        agg.update_component("a", HealthStatus.DEGRADED)
        for _ in range(5):
            agg.compute()
        # Now jump to healthy
        agg.update_component("a", HealthStatus.HEALTHY)
        result = agg.compute()
        assert result.trend == HealthTrend.IMPROVING

    def test_declining_trend(self):
        agg = _make_agg()
        agg.register("a")
        # Build history with high scores
        agg.update_component("a", HealthStatus.HEALTHY)
        for _ in range(5):
            agg.compute()
        # Now drop to unhealthy
        agg.update_component("a", HealthStatus.UNHEALTHY)
        result = agg.compute()
        assert result.trend == HealthTrend.DECLINING

    def test_stable_trend_with_consistent_scores(self):
        agg = _make_agg()
        agg.register("a")
        agg.update_component("a", HealthStatus.HEALTHY)
        for _ in range(5):
            agg.compute()
        # Still healthy
        result = agg.compute()
        assert result.trend == HealthTrend.STABLE


# =========================================================================
# History tracking and get_history()
# =========================================================================


class TestHistory:
    def test_compute_adds_to_history(self):
        agg = _make_agg()
        agg.register("a")
        agg.update_component("a", HealthStatus.HEALTHY)
        agg.compute()

        history = agg.get_history()
        assert len(history) == 1
        assert isinstance(history[0], HealthSnapshot)

    def test_history_bounded(self):
        agg = _make_agg(history_size=5)
        agg.register("a")
        agg.update_component("a", HealthStatus.HEALTHY)
        for _ in range(10):
            agg.compute()
        history = agg.get_history()
        assert len(history) <= 5

    def test_get_history_limit(self):
        agg = _make_agg()
        agg.register("a")
        agg.update_component("a", HealthStatus.HEALTHY)
        for _ in range(10):
            agg.compute()
        history = agg.get_history(limit=3)
        assert len(history) == 3

    def test_history_contains_score(self):
        agg = _make_agg()
        agg.register("a")
        agg.update_component("a", HealthStatus.HEALTHY)
        agg.compute()
        snap = agg.get_history()[0]
        assert snap.health_score == 100.0

    def test_history_contains_status(self):
        agg = _make_agg()
        agg.register("a")
        agg.update_component("a", HealthStatus.HEALTHY)
        agg.compute()
        snap = agg.get_history()[0]
        assert snap.overall_status == HealthStatus.HEALTHY

    def test_history_contains_component_count(self):
        agg = _make_agg()
        agg.register("a")
        agg.register("b")
        agg.update_component("a", HealthStatus.HEALTHY)
        agg.update_component("b", HealthStatus.HEALTHY)
        agg.compute()
        snap = agg.get_history()[0]
        assert snap.component_count == 2


# =========================================================================
# update_component() tracks consecutive_failures
# =========================================================================


class TestUpdateComponent:
    def test_unhealthy_increments_failures(self):
        agg = _make_agg()
        agg.register("db")
        agg.update_component("db", HealthStatus.UNHEALTHY)
        agg.update_component("db", HealthStatus.UNHEALTHY)

        comp = agg.get_component("db")
        assert comp.consecutive_failures == 2

    def test_critical_increments_failures(self):
        agg = _make_agg()
        agg.register("db")
        agg.update_component("db", HealthStatus.CRITICAL)

        comp = agg.get_component("db")
        assert comp.consecutive_failures == 1

    def test_healthy_resets_failures(self):
        agg = _make_agg()
        agg.register("db")
        agg.update_component("db", HealthStatus.UNHEALTHY)
        agg.update_component("db", HealthStatus.UNHEALTHY)
        agg.update_component("db", HealthStatus.HEALTHY)

        comp = agg.get_component("db")
        assert comp.consecutive_failures == 0

    def test_degraded_resets_failures(self):
        agg = _make_agg()
        agg.register("db")
        agg.update_component("db", HealthStatus.UNHEALTHY)
        agg.update_component("db", HealthStatus.DEGRADED)

        comp = agg.get_component("db")
        assert comp.consecutive_failures == 0

    def test_update_sets_latency(self):
        agg = _make_agg()
        agg.register("db")
        agg.update_component("db", HealthStatus.HEALTHY, latency_ms=42.5)

        comp = agg.get_component("db")
        assert comp.latency_ms == 42.5

    def test_update_sets_message(self):
        agg = _make_agg()
        agg.register("db")
        agg.update_component("db", HealthStatus.UNHEALTHY, message="timeout")

        comp = agg.get_component("db")
        assert comp.message == "timeout"

    def test_update_nonexistent_returns_none(self):
        agg = _make_agg()
        result = agg.update_component("nope", HealthStatus.HEALTHY)
        assert result is None

    def test_update_sets_last_checked(self):
        agg = _make_agg()
        agg.register("db")
        before = time.time()
        agg.update_component("db", HealthStatus.HEALTHY)
        comp = agg.get_component("db")
        assert comp.last_checked >= before


# =========================================================================
# Empty components
# =========================================================================


class TestEmptyComponents:
    def test_default_aggregate_health(self):
        agg = _make_agg()
        result = agg.compute()
        assert isinstance(result, AggregateHealth)
        assert result.overall_status == HealthStatus.UNKNOWN
        assert result.health_score == 0.0
        assert result.components == []

    def test_trend_stable_on_empty(self):
        agg = _make_agg()
        result = agg.compute()
        assert result.trend == HealthTrend.STABLE


# =========================================================================
# Stats by status
# =========================================================================


class TestGetStats:
    def test_empty_stats(self):
        agg = _make_agg()
        stats = agg.get_stats()
        assert stats["total_components"] == 0
        assert stats["by_status"] == {}
        assert stats["history_size"] == 0

    def test_counts_by_status(self):
        agg = _make_agg()
        agg.register("a")
        agg.register("b")
        agg.update_component("a", HealthStatus.HEALTHY)
        agg.update_component("b", HealthStatus.UNHEALTHY)

        stats = agg.get_stats()
        assert stats["total_components"] == 2
        assert stats["by_status"]["healthy"] == 1
        assert stats["by_status"]["unhealthy"] == 1

    def test_history_size_in_stats(self):
        agg = _make_agg()
        agg.register("a")
        agg.update_component("a", HealthStatus.HEALTHY)
        agg.compute()
        agg.compute()

        stats = agg.get_stats()
        assert stats["history_size"] == 2


# =========================================================================
# Multiple components with different weights
# =========================================================================


class TestMultipleWeights:
    def test_higher_weight_dominates_score(self):
        agg = _make_agg()
        agg.register("important", weight=10.0)
        agg.register("minor", weight=1.0)
        agg.update_component("important", HealthStatus.HEALTHY)
        agg.update_component("minor", HealthStatus.UNHEALTHY)

        result = agg.compute()
        # (10*1.0 + 1*0.1) / 11 * 100 = 91.82 -> HEALTHY
        assert result.health_score == pytest.approx(91.82, abs=0.01)
        assert result.overall_status == HealthStatus.HEALTHY

    def test_equal_weights(self):
        agg = _make_agg()
        agg.register("a", weight=1.0)
        agg.register("b", weight=1.0)
        agg.update_component("a", HealthStatus.HEALTHY)
        agg.update_component("b", HealthStatus.UNHEALTHY)

        result = agg.compute()
        assert result.health_score == 55.0

    def test_zero_weight_component(self):
        agg = _make_agg()
        agg.register("a", weight=0.0)
        agg.register("b", weight=1.0)
        agg.update_component("a", HealthStatus.UNHEALTHY)
        agg.update_component("b", HealthStatus.HEALTHY)

        result = agg.compute()
        # (0*0.1 + 1*1.0) / 1 * 100 = 100
        assert result.health_score == 100.0


# =========================================================================
# Model tests
# =========================================================================


class TestModels:
    def test_component_health_defaults(self):
        c = ComponentHealth(name="test")
        assert c.status == HealthStatus.UNKNOWN
        assert c.weight == 1.0
        assert c.is_critical is False
        assert c.consecutive_failures == 0

    def test_health_snapshot_defaults(self):
        s = HealthSnapshot()
        assert s.health_score == 0.0
        assert s.overall_status == HealthStatus.UNKNOWN

    def test_aggregate_health_defaults(self):
        a = AggregateHealth()
        assert a.overall_status == HealthStatus.UNKNOWN
        assert a.health_score == 0.0
        assert a.trend == HealthTrend.STABLE

    def test_health_status_values(self):
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"
        assert HealthStatus.CRITICAL == "critical"
        assert HealthStatus.UNKNOWN == "unknown"

    def test_health_trend_values(self):
        assert HealthTrend.IMPROVING == "improving"
        assert HealthTrend.STABLE == "stable"
        assert HealthTrend.DECLINING == "declining"
