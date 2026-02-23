"""Tests for shieldops.policy.rollback.registry -- RollbackRegistry."""

from __future__ import annotations

import time

import pytest

from shieldops.policy.rollback.registry import (
    RollbackEvent,
    RollbackPattern,
    RollbackRegistry,
    RollbackResult,
    RollbackTrigger,
    RollbackType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _registry(**kwargs) -> RollbackRegistry:
    return RollbackRegistry(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_rollback_result_success(self):
        assert RollbackResult.SUCCESS == "success"

    def test_rollback_result_partial(self):
        assert RollbackResult.PARTIAL == "partial"

    def test_rollback_result_failed(self):
        assert RollbackResult.FAILED == "failed"

    def test_rollback_type_deployment(self):
        assert RollbackType.DEPLOYMENT == "deployment"

    def test_rollback_type_config(self):
        assert RollbackType.CONFIG == "config"

    def test_rollback_type_infrastructure(self):
        assert RollbackType.INFRASTRUCTURE == "infrastructure"

    def test_rollback_type_database(self):
        assert RollbackType.DATABASE == "database"

    def test_rollback_type_feature_flag(self):
        assert RollbackType.FEATURE_FLAG == "feature_flag"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_rollback_event_defaults(self):
        e = RollbackEvent(service="api", rollback_type=RollbackType.DEPLOYMENT)
        assert e.id
        assert e.service == "api"
        assert e.rollback_type == RollbackType.DEPLOYMENT
        assert e.result == RollbackResult.SUCCESS
        assert e.trigger_reason == ""
        assert e.from_version == ""
        assert e.to_version == ""
        assert e.duration_seconds == 0.0
        assert e.initiated_by == ""
        assert e.metadata == {}

    def test_rollback_trigger_fields(self):
        t = RollbackTrigger(trigger_reason="high_error_rate", count=5)
        assert t.trigger_reason == "high_error_rate"
        assert t.count == 5
        assert t.services == []

    def test_rollback_pattern_fields(self):
        p = RollbackPattern(
            pattern="repeated_rollback:api",
            frequency=3,
            avg_duration=12.5,
        )
        assert p.pattern == "repeated_rollback:api"
        assert p.frequency == 3
        assert p.services == []
        assert p.avg_duration == 12.5
        assert p.recommendation == ""


# ---------------------------------------------------------------------------
# Record rollback
# ---------------------------------------------------------------------------


class TestRecordRollback:
    def test_record_basic(self):
        r = _registry()
        evt = r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        assert evt.service == "api"
        assert evt.id
        assert evt.rollback_type == RollbackType.DEPLOYMENT

    def test_record_with_all_fields(self):
        r = _registry()
        evt = r.record_rollback(
            service="payment",
            rollback_type=RollbackType.CONFIG,
            result=RollbackResult.PARTIAL,
            trigger_reason="high_latency",
            from_version="v2.1.0",
            to_version="v2.0.9",
            duration_seconds=45.3,
            initiated_by="oncall-bot",
            metadata={"region": "us-east-1"},
        )
        assert evt.result == RollbackResult.PARTIAL
        assert evt.trigger_reason == "high_latency"
        assert evt.from_version == "v2.1.0"
        assert evt.to_version == "v2.0.9"
        assert evt.duration_seconds == 45.3
        assert evt.initiated_by == "oncall-bot"
        assert evt.metadata["region"] == "us-east-1"

    def test_record_max_limit(self):
        r = _registry(max_events=2)
        r.record_rollback(service="s1", rollback_type=RollbackType.DEPLOYMENT)
        r.record_rollback(service="s2", rollback_type=RollbackType.DEPLOYMENT)
        with pytest.raises(ValueError, match="Maximum events"):
            r.record_rollback(service="s3", rollback_type=RollbackType.DEPLOYMENT)

    def test_record_unique_ids(self):
        r = _registry()
        e1 = r.record_rollback(service="a", rollback_type=RollbackType.DEPLOYMENT)
        e2 = r.record_rollback(service="b", rollback_type=RollbackType.DEPLOYMENT)
        assert e1.id != e2.id


# ---------------------------------------------------------------------------
# Get rollback
# ---------------------------------------------------------------------------


class TestGetRollback:
    def test_get_found(self):
        r = _registry()
        evt = r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        result = r.get_rollback(evt.id)
        assert result is not None
        assert result.service == "api"

    def test_get_not_found(self):
        r = _registry()
        assert r.get_rollback("nonexistent") is None


# ---------------------------------------------------------------------------
# List rollbacks
# ---------------------------------------------------------------------------


class TestListRollbacks:
    def test_list_all(self):
        r = _registry()
        r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        r.record_rollback(service="web", rollback_type=RollbackType.CONFIG)
        assert len(r.list_rollbacks()) == 2

    def test_list_filter_by_service(self):
        r = _registry()
        r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        r.record_rollback(service="web", rollback_type=RollbackType.CONFIG)
        r.record_rollback(service="api", rollback_type=RollbackType.CONFIG)
        filtered = r.list_rollbacks(service="api")
        assert len(filtered) == 2

    def test_list_filter_by_type(self):
        r = _registry()
        r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        r.record_rollback(service="web", rollback_type=RollbackType.CONFIG)
        r.record_rollback(service="db", rollback_type=RollbackType.DEPLOYMENT)
        filtered = r.list_rollbacks(rollback_type=RollbackType.DEPLOYMENT)
        assert len(filtered) == 2

    def test_list_filter_by_service_and_type(self):
        r = _registry()
        r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        r.record_rollback(service="api", rollback_type=RollbackType.CONFIG)
        r.record_rollback(service="web", rollback_type=RollbackType.DEPLOYMENT)
        filtered = r.list_rollbacks(service="api", rollback_type=RollbackType.DEPLOYMENT)
        assert len(filtered) == 1

    def test_list_empty(self):
        r = _registry()
        assert r.list_rollbacks() == []


# ---------------------------------------------------------------------------
# Delete rollback
# ---------------------------------------------------------------------------


class TestDeleteRollback:
    def test_delete_success(self):
        r = _registry()
        evt = r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        assert r.delete_rollback(evt.id) is True
        assert r.get_rollback(evt.id) is None

    def test_delete_not_found(self):
        r = _registry()
        assert r.delete_rollback("nonexistent") is False


# ---------------------------------------------------------------------------
# Analyze triggers
# ---------------------------------------------------------------------------


class TestAnalyzeTriggers:
    def test_groups_by_reason(self):
        r = _registry()
        r.record_rollback(
            service="api",
            rollback_type=RollbackType.DEPLOYMENT,
            trigger_reason="high_error_rate",
        )
        r.record_rollback(
            service="web",
            rollback_type=RollbackType.DEPLOYMENT,
            trigger_reason="high_error_rate",
        )
        r.record_rollback(
            service="api",
            rollback_type=RollbackType.CONFIG,
            trigger_reason="memory_leak",
        )
        triggers = r.analyze_triggers()
        assert len(triggers) == 2
        assert triggers[0].trigger_reason == "high_error_rate"
        assert triggers[0].count == 2

    def test_counts_correct(self):
        r = _registry()
        for _ in range(3):
            r.record_rollback(
                service="api",
                rollback_type=RollbackType.DEPLOYMENT,
                trigger_reason="timeout",
            )
        triggers = r.analyze_triggers()
        assert triggers[0].count == 3

    def test_lists_services(self):
        r = _registry()
        r.record_rollback(
            service="api",
            rollback_type=RollbackType.DEPLOYMENT,
            trigger_reason="cpu_spike",
        )
        r.record_rollback(
            service="web",
            rollback_type=RollbackType.DEPLOYMENT,
            trigger_reason="cpu_spike",
        )
        triggers = r.analyze_triggers()
        assert "api" in triggers[0].services
        assert "web" in triggers[0].services

    def test_skips_empty_trigger_reason(self):
        r = _registry()
        r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        triggers = r.analyze_triggers()
        assert len(triggers) == 0

    def test_empty_registry(self):
        r = _registry()
        assert r.analyze_triggers() == []


# ---------------------------------------------------------------------------
# Detect patterns
# ---------------------------------------------------------------------------


class TestDetectPatterns:
    def test_finds_repeat_offenders(self):
        r = _registry()
        r.record_rollback(
            service="api",
            rollback_type=RollbackType.DEPLOYMENT,
            duration_seconds=10.0,
        )
        r.record_rollback(
            service="api",
            rollback_type=RollbackType.DEPLOYMENT,
            duration_seconds=20.0,
        )
        patterns = r.detect_patterns()
        assert len(patterns) == 1
        assert patterns[0].pattern == "repeated_rollback:api"
        assert patterns[0].frequency == 2
        assert patterns[0].avg_duration == 15.0

    def test_no_patterns_when_single_rollback(self):
        r = _registry()
        r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        patterns = r.detect_patterns()
        assert len(patterns) == 0

    def test_recommendation_for_frequent_rollbacks(self):
        r = _registry()
        for _ in range(5):
            r.record_rollback(
                service="payment",
                rollback_type=RollbackType.DEPLOYMENT,
                duration_seconds=5.0,
            )
        patterns = r.detect_patterns()
        assert len(patterns) == 1
        assert "5 rollbacks" in patterns[0].recommendation
        assert "payment" in patterns[0].recommendation

    def test_recommendation_for_moderate_rollbacks(self):
        r = _registry()
        r.record_rollback(service="web", rollback_type=RollbackType.DEPLOYMENT)
        r.record_rollback(service="web", rollback_type=RollbackType.DEPLOYMENT)
        patterns = r.detect_patterns()
        assert "repeated rollbacks" in patterns[0].recommendation

    def test_sorted_by_frequency(self):
        r = _registry()
        for _ in range(3):
            r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        for _ in range(5):
            r.record_rollback(service="web", rollback_type=RollbackType.DEPLOYMENT)
        patterns = r.detect_patterns()
        assert patterns[0].frequency >= patterns[1].frequency

    def test_excludes_old_events_outside_lookback(self):
        r = _registry(pattern_lookback_days=1)
        old_event = r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        old_event.created_at = time.time() - 3 * 86400
        r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        patterns = r.detect_patterns()
        assert len(patterns) == 0


# ---------------------------------------------------------------------------
# Success rate
# ---------------------------------------------------------------------------


class TestGetSuccessRate:
    def test_success_rate_all(self):
        r = _registry()
        r.record_rollback(
            service="api",
            rollback_type=RollbackType.DEPLOYMENT,
            result=RollbackResult.SUCCESS,
        )
        r.record_rollback(
            service="api",
            rollback_type=RollbackType.DEPLOYMENT,
            result=RollbackResult.FAILED,
        )
        rate = r.get_success_rate()
        assert rate["total"] == 2
        assert rate["success_count"] == 1
        assert rate["failed_count"] == 1
        assert rate["success_rate"] == 0.5

    def test_success_rate_by_service(self):
        r = _registry()
        r.record_rollback(
            service="api",
            rollback_type=RollbackType.DEPLOYMENT,
            result=RollbackResult.SUCCESS,
        )
        r.record_rollback(
            service="web",
            rollback_type=RollbackType.DEPLOYMENT,
            result=RollbackResult.FAILED,
        )
        rate = r.get_success_rate(service="api")
        assert rate["total"] == 1
        assert rate["success_count"] == 1
        assert rate["success_rate"] == 1.0

    def test_success_rate_empty(self):
        r = _registry()
        rate = r.get_success_rate()
        assert rate["total"] == 0
        assert rate["success_rate"] == 0.0

    def test_success_rate_with_partial(self):
        r = _registry()
        r.record_rollback(
            service="api",
            rollback_type=RollbackType.DEPLOYMENT,
            result=RollbackResult.PARTIAL,
        )
        rate = r.get_success_rate()
        assert rate["partial_count"] == 1
        assert rate["success_rate"] == 0.0


# ---------------------------------------------------------------------------
# Get rollback by service
# ---------------------------------------------------------------------------


class TestGetRollbackByService:
    def test_get_by_service_success(self):
        r = _registry()
        r.record_rollback(service="api", rollback_type=RollbackType.DEPLOYMENT)
        r.record_rollback(service="api", rollback_type=RollbackType.CONFIG)
        r.record_rollback(service="web", rollback_type=RollbackType.DEPLOYMENT)
        results = r.get_rollback_by_service("api")
        assert len(results) == 2
        assert all(e.service == "api" for e in results)

    def test_get_by_service_empty(self):
        r = _registry()
        assert r.get_rollback_by_service("api") == []


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        r = _registry()
        s = r.get_stats()
        assert s["total_events"] == 0
        assert s["successful_rollbacks"] == 0
        assert s["unique_services"] == 0

    def test_stats_with_data(self):
        r = _registry()
        r.record_rollback(
            service="api",
            rollback_type=RollbackType.DEPLOYMENT,
            result=RollbackResult.SUCCESS,
        )
        r.record_rollback(
            service="web",
            rollback_type=RollbackType.CONFIG,
            result=RollbackResult.FAILED,
        )
        s = r.get_stats()
        assert s["total_events"] == 2
        assert s["successful_rollbacks"] == 1
        assert s["unique_services"] == 2

    def test_stats_includes_lookback_days(self):
        r = _registry(pattern_lookback_days=30)
        s = r.get_stats()
        assert s["pattern_lookback_days"] == 30
