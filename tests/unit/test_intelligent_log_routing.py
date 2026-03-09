"""Tests for shieldops.observability.intelligent_log_routing — IntelligentLogRouting."""

from __future__ import annotations

from shieldops.observability.intelligent_log_routing import (
    IntelligentLogRouting,
    LogCategory,
    LogRoutingRecord,
    LogRoutingReport,
    LogTier,
    RoutingRule,
    RoutingStrategy,
)


def _engine(**kw) -> IntelligentLogRouting:
    return IntelligentLogRouting(**kw)


class TestEnums:
    def test_log_tier_hot(self):
        assert LogTier.HOT == "hot"

    def test_log_tier_warm(self):
        assert LogTier.WARM == "warm"

    def test_log_tier_cold(self):
        assert LogTier.COLD == "cold"

    def test_log_tier_archive(self):
        assert LogTier.ARCHIVE == "archive"

    def test_log_tier_drop(self):
        assert LogTier.DROP == "drop"

    def test_log_category_error(self):
        assert LogCategory.ERROR == "error"

    def test_log_category_warning(self):
        assert LogCategory.WARNING == "warning"

    def test_log_category_info(self):
        assert LogCategory.INFO == "info"

    def test_log_category_debug(self):
        assert LogCategory.DEBUG == "debug"

    def test_log_category_audit(self):
        assert LogCategory.AUDIT == "audit"

    def test_routing_strategy_content(self):
        assert RoutingStrategy.CONTENT_BASED == "content_based"


class TestModels:
    def test_record_defaults(self):
        r = LogRoutingRecord()
        assert r.id
        assert r.category == LogCategory.INFO
        assert r.tier == LogTier.WARM

    def test_rule_defaults(self):
        r = RoutingRule()
        assert r.id
        assert r.enabled is True

    def test_report_defaults(self):
        r = LogRoutingReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        rule = eng.add_rule("error-to-hot", pattern="error", target_tier=LogTier.HOT)
        assert rule.name == "error-to-hot"
        assert rule.target_tier == LogTier.HOT


class TestClassifyLog:
    def test_error(self):
        eng = _engine()
        r = eng.classify_log("app", "NullPointer error occurred")
        assert r.category == LogCategory.ERROR
        assert r.tier == LogTier.HOT

    def test_warning(self):
        eng = _engine()
        r = eng.classify_log("app", "warn: high latency")
        assert r.category == LogCategory.WARNING
        assert r.tier == LogTier.WARM

    def test_audit(self):
        eng = _engine()
        r = eng.classify_log("app", "audit: user login")
        assert r.category == LogCategory.AUDIT
        assert r.tier == LogTier.HOT

    def test_debug(self):
        eng = _engine()
        r = eng.classify_log("app", "debug: variable x=5")
        assert r.category == LogCategory.DEBUG

    def test_info(self):
        eng = _engine()
        r = eng.classify_log("app", "request processed successfully")
        assert r.category == LogCategory.INFO

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.classify_log(f"src-{i}", "info msg")
        assert len(eng._records) == 3

    def test_exception_classified_as_error(self):
        eng = _engine()
        r = eng.classify_log("app", "exception in handler")
        assert r.category == LogCategory.ERROR


class TestRouteToTier:
    def test_basic(self):
        eng = _engine()
        result = eng.route_to_tier("app", "error happened")
        assert result["tier"] == "hot"
        assert result["category"] == "error"

    def test_rule_override(self):
        eng = _engine()
        eng.add_rule("force-cold", pattern="force-cold", target_tier=LogTier.COLD, priority=10)
        result = eng.route_to_tier("app", "force-cold log line")
        assert result["tier"] == "cold"


class TestOptimizeRoutingRules:
    def test_no_suggestions(self):
        eng = _engine()
        result = eng.optimize_routing_rules()
        assert result[0]["type"] == "none"

    def test_high_hot_volume(self):
        eng = _engine()
        for _ in range(10):
            eng.classify_log("app", "error", volume_bytes=200_000)
        result = eng.optimize_routing_rules()
        assert any(s["type"] == "downgrade" for s in result)

    def test_high_debug_ratio(self):
        eng = _engine()
        for _ in range(10):
            eng.classify_log("app", "debug: x")
        for _ in range(2):
            eng.classify_log("app", "info msg")
        result = eng.optimize_routing_rules()
        assert any(s["type"] == "filter" for s in result)


class TestEstimateStorageImpact:
    def test_empty(self):
        eng = _engine()
        result = eng.estimate_storage_impact()
        assert result["total_cost"] == 0

    def test_with_data(self):
        eng = _engine()
        eng.classify_log("app", "error", volume_bytes=1024 * 1024 * 1024)
        result = eng.estimate_storage_impact()
        assert result["total_cost"] > 0


class TestGetRoutingStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_routing_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.classify_log("app", "test")
        eng.add_rule("r1", pattern="x")
        stats = eng.get_routing_stats()
        assert stats["total_records"] == 1
        assert stats["total_rules"] == 1


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0

    def test_populated(self):
        eng = _engine()
        eng.classify_log("app", "error")
        report = eng.generate_report()
        assert report.total_records == 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.classify_log("app", "test")
        eng.add_rule("r1")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0
