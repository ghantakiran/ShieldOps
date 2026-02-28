"""Tests for shieldops.observability.alert_dedup — AlertDeduplicationEngine."""

from __future__ import annotations

from shieldops.observability.alert_dedup import (
    AlertDeduplicationEngine,
    AlertDedupReport,
    AlertPriority,
    DedupRecord,
    DedupResult,
    DedupRule,
    DedupStrategy,
)


def _engine(**kw) -> AlertDeduplicationEngine:
    return AlertDeduplicationEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DedupStrategy (5)
    def test_strategy_exact_match(self):
        assert DedupStrategy.EXACT_MATCH == "exact_match"

    def test_strategy_fuzzy_match(self):
        assert DedupStrategy.FUZZY_MATCH == "fuzzy_match"

    def test_strategy_time_window(self):
        assert DedupStrategy.TIME_WINDOW == "time_window"

    def test_strategy_fingerprint(self):
        assert DedupStrategy.FINGERPRINT == "fingerprint"

    def test_strategy_content_hash(self):
        assert DedupStrategy.CONTENT_HASH == "content_hash"

    # DedupResult (5)
    def test_result_duplicate(self):
        assert DedupResult.DUPLICATE == "duplicate"

    def test_result_unique(self):
        assert DedupResult.UNIQUE == "unique"

    def test_result_near_duplicate(self):
        assert DedupResult.NEAR_DUPLICATE == "near_duplicate"

    def test_result_superseded(self):
        assert DedupResult.SUPERSEDED == "superseded"

    def test_result_merged(self):
        assert DedupResult.MERGED == "merged"

    # AlertPriority (5)
    def test_priority_critical(self):
        assert AlertPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert AlertPriority.HIGH == "high"

    def test_priority_medium(self):
        assert AlertPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert AlertPriority.LOW == "low"

    def test_priority_info(self):
        assert AlertPriority.INFO == "info"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_dedup_record_defaults(self):
        r = DedupRecord()
        assert r.id
        assert r.alert_name == ""
        assert r.source == ""
        assert r.fingerprint == ""
        assert r.strategy == DedupStrategy.EXACT_MATCH
        assert r.result == DedupResult.UNIQUE
        assert r.priority == AlertPriority.MEDIUM
        assert r.duplicate_count == 0
        assert r.suppressed is False
        assert r.created_at > 0

    def test_dedup_rule_defaults(self):
        r = DedupRule()
        assert r.id
        assert r.rule_name == ""
        assert r.strategy == DedupStrategy.EXACT_MATCH
        assert r.time_window_seconds == 300.0
        assert r.match_fields == []
        assert r.enabled is True
        assert r.created_at > 0

    def test_report_defaults(self):
        r = AlertDedupReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.duplicate_count == 0
        assert r.unique_count == 0
        assert r.suppression_rate_pct == 0.0
        assert r.by_strategy == {}
        assert r.by_result == {}
        assert r.by_priority == {}
        assert r.top_duplicate_sources == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_dedup
# -------------------------------------------------------------------


class TestRecordDedup:
    def test_basic(self):
        eng = _engine()
        r = eng.record_dedup("cpu-alert")
        assert r.alert_name == "cpu-alert"
        assert r.result == DedupResult.UNIQUE

    def test_with_params(self):
        eng = _engine()
        r = eng.record_dedup(
            "disk-alert",
            source="prometheus",
            fingerprint="abc123",
            strategy=DedupStrategy.FINGERPRINT,
            result=DedupResult.DUPLICATE,
            priority=AlertPriority.CRITICAL,
            duplicate_count=5,
            suppressed=True,
        )
        assert r.strategy == DedupStrategy.FINGERPRINT
        assert r.result == DedupResult.DUPLICATE
        assert r.duplicate_count == 5
        assert r.suppressed is True

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_dedup("alert-a")
        r2 = eng.record_dedup("alert-b")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_dedup(f"alert-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_dedup
# -------------------------------------------------------------------


class TestGetDedup:
    def test_found(self):
        eng = _engine()
        r = eng.record_dedup("test-alert")
        assert eng.get_dedup(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_dedup("nonexistent") is None


# -------------------------------------------------------------------
# list_dedups
# -------------------------------------------------------------------


class TestListDedups:
    def test_list_all(self):
        eng = _engine()
        eng.record_dedup("alert-a")
        eng.record_dedup("alert-b")
        assert len(eng.list_dedups()) == 2

    def test_filter_by_strategy(self):
        eng = _engine()
        eng.record_dedup("alert-a", strategy=DedupStrategy.EXACT_MATCH)
        eng.record_dedup("alert-b", strategy=DedupStrategy.FUZZY_MATCH)
        results = eng.list_dedups(strategy=DedupStrategy.FUZZY_MATCH)
        assert len(results) == 1
        assert results[0].strategy == DedupStrategy.FUZZY_MATCH

    def test_filter_by_result(self):
        eng = _engine()
        eng.record_dedup("alert-a", result=DedupResult.DUPLICATE)
        eng.record_dedup("alert-b", result=DedupResult.UNIQUE)
        results = eng.list_dedups(result=DedupResult.DUPLICATE)
        assert len(results) == 1

    def test_filter_by_priority(self):
        eng = _engine()
        eng.record_dedup("alert-a", priority=AlertPriority.CRITICAL)
        eng.record_dedup("alert-b", priority=AlertPriority.LOW)
        results = eng.list_dedups(priority=AlertPriority.CRITICAL)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_dedup(f"alert-{i}")
        assert len(eng.list_dedups(limit=5)) == 5


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        rule = eng.add_rule("dedup-by-name")
        assert rule.rule_name == "dedup-by-name"
        assert rule.strategy == DedupStrategy.EXACT_MATCH
        assert rule.enabled is True

    def test_with_params(self):
        eng = _engine()
        rule = eng.add_rule(
            "time-window-rule",
            strategy=DedupStrategy.TIME_WINDOW,
            time_window_seconds=600.0,
            match_fields=["service", "severity"],
        )
        assert rule.strategy == DedupStrategy.TIME_WINDOW
        assert rule.time_window_seconds == 600.0
        assert "service" in rule.match_fields

    def test_unique_rule_ids(self):
        eng = _engine()
        r1 = eng.add_rule("rule-a")
        r2 = eng.add_rule("rule-b")
        assert r1.id != r2.id


# -------------------------------------------------------------------
# analyze_dedup_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeDedupEffectiveness:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_dedup_effectiveness()
        assert result["total"] == 0
        assert result["dedup_ratio_pct"] == 0.0

    def test_with_duplicates(self):
        eng = _engine()
        eng.record_dedup("alert-a", result=DedupResult.DUPLICATE)
        eng.record_dedup("alert-b", result=DedupResult.DUPLICATE)
        eng.record_dedup("alert-c", result=DedupResult.UNIQUE)
        result = eng.analyze_dedup_effectiveness()
        assert result["total"] == 3
        assert result["duplicates"] == 2
        assert result["dedup_ratio_pct"] > 0.0

    def test_meets_threshold(self):
        eng = _engine(min_dedup_ratio_pct=50.0)
        for _ in range(6):
            eng.record_dedup("alert", result=DedupResult.DUPLICATE)
        for _ in range(4):
            eng.record_dedup("alert", result=DedupResult.UNIQUE)
        result = eng.analyze_dedup_effectiveness()
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_high_duplicate_sources
# -------------------------------------------------------------------


class TestIdentifyHighDuplicateSources:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_duplicate_sources() == []

    def test_with_data(self):
        eng = _engine()
        for _ in range(5):
            eng.record_dedup("cpu-high", source="datadog", result=DedupResult.DUPLICATE)
        eng.record_dedup("mem-low", source="prometheus", result=DedupResult.UNIQUE)
        results = eng.identify_high_duplicate_sources()
        assert len(results) >= 1
        assert results[0]["source"] == "datadog"
        assert results[0]["duplicate_count"] == 5

    def test_sorted_descending(self):
        eng = _engine()
        for _ in range(3):
            eng.record_dedup("alert", source="source-a", result=DedupResult.DUPLICATE)
        for _ in range(7):
            eng.record_dedup("alert", source="source-b", result=DedupResult.DUPLICATE)
        results = eng.identify_high_duplicate_sources()
        assert results[0]["duplicate_count"] >= results[-1]["duplicate_count"]


# -------------------------------------------------------------------
# rank_by_dedup_ratio
# -------------------------------------------------------------------


class TestRankByDedupRatio:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_dedup_ratio() == []

    def test_sorted_by_ratio(self):
        eng = _engine()
        for _ in range(9):
            eng.record_dedup("high-dupe-alert", result=DedupResult.DUPLICATE)
        eng.record_dedup("high-dupe-alert", result=DedupResult.UNIQUE)
        for _ in range(5):
            eng.record_dedup("low-dupe-alert", result=DedupResult.UNIQUE)
        results = eng.rank_by_dedup_ratio()
        assert results[0]["dedup_ratio_pct"] >= results[-1]["dedup_ratio_pct"]
        assert results[0]["alert_name"] == "high-dupe-alert"


# -------------------------------------------------------------------
# detect_dedup_trends
# -------------------------------------------------------------------


class TestDetectDedupTrends:
    def test_insufficient_data(self):
        eng = _engine()
        eng.record_dedup("alert-a")
        result = eng.detect_dedup_trends()
        assert result["trend"] == "insufficient_data"

    def test_stable_trend(self):
        eng = _engine()
        for _ in range(4):
            eng.record_dedup("alert", result=DedupResult.DUPLICATE)
        for _ in range(4):
            eng.record_dedup("alert", result=DedupResult.DUPLICATE)
        result = eng.detect_dedup_trends()
        assert result["trend"] in ("stable", "improving", "worsening")

    def test_worsening_trend(self):
        eng = _engine()
        # First half: mostly unique
        for _ in range(8):
            eng.record_dedup("alert", result=DedupResult.UNIQUE)
        # Second half: mostly duplicate
        for _ in range(8):
            eng.record_dedup("alert", result=DedupResult.DUPLICATE)
        result = eng.detect_dedup_trends()
        assert result["trend"] == "worsening"
        assert result["total_records"] == 16


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert isinstance(report, AlertDedupReport)
        assert report.total_records == 0
        assert report.recommendations

    def test_with_data(self):
        eng = _engine()
        eng.add_rule("fingerprint-rule", strategy=DedupStrategy.FINGERPRINT)
        eng.record_dedup("alert-a", source="prom", result=DedupResult.DUPLICATE)
        eng.record_dedup("alert-b", source="prom", result=DedupResult.UNIQUE)
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_rules == 1
        assert report.duplicate_count == 1
        assert report.unique_count == 1
        assert report.by_result


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_records_and_rules(self):
        eng = _engine()
        eng.record_dedup("alert-a")
        eng.add_rule("rule-a")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["suppressed_count"] == 0

    def test_populated(self):
        eng = _engine(min_dedup_ratio_pct=60.0)
        eng.record_dedup("alert-a", source="datadog", result=DedupResult.DUPLICATE, suppressed=True)
        eng.record_dedup("alert-b", source="prometheus", result=DedupResult.UNIQUE)
        eng.add_rule("rule-a")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_rules"] == 1
        assert stats["suppressed_count"] == 1
        assert stats["min_dedup_ratio_pct"] == 60.0
        assert stats["unique_sources"] == 2
