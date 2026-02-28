"""Tests for shieldops.config.flag_impact — FeatureFlagImpactAnalyzer."""

from __future__ import annotations

from shieldops.config.flag_impact import (
    FeatureFlagImpactAnalyzer,
    FlagAnalysis,
    FlagCategory,
    FlagImpactRecord,
    FlagImpactReport,
    ImpactLevel,
    ImpactType,
)


def _engine(**kw) -> FeatureFlagImpactAnalyzer:
    return FeatureFlagImpactAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # FlagCategory (5)
    def test_category_release(self):
        assert FlagCategory.RELEASE == "release"

    def test_category_experiment(self):
        assert FlagCategory.EXPERIMENT == "experiment"

    def test_category_operational(self):
        assert FlagCategory.OPERATIONAL == "operational"

    def test_category_permission(self):
        assert FlagCategory.PERMISSION == "permission"

    def test_category_kill_switch(self):
        assert FlagCategory.KILL_SWITCH == "kill_switch"

    # ImpactLevel (5)
    def test_impact_critical(self):
        assert ImpactLevel.CRITICAL == "critical"

    def test_impact_high(self):
        assert ImpactLevel.HIGH == "high"

    def test_impact_moderate(self):
        assert ImpactLevel.MODERATE == "moderate"

    def test_impact_low(self):
        assert ImpactLevel.LOW == "low"

    def test_impact_none_detected(self):
        assert ImpactLevel.NONE_DETECTED == "none_detected"

    # ImpactType (5)
    def test_type_latency_increase(self):
        assert ImpactType.LATENCY_INCREASE == "latency_increase"

    def test_type_error_rate(self):
        assert ImpactType.ERROR_RATE == "error_rate"

    def test_type_reliability_drop(self):
        assert ImpactType.RELIABILITY_DROP == "reliability_drop"

    def test_type_performance_gain(self):
        assert ImpactType.PERFORMANCE_GAIN == "performance_gain"

    def test_type_neutral(self):
        assert ImpactType.NEUTRAL == "neutral"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_flag_impact_record_defaults(self):
        r = FlagImpactRecord()
        assert r.id
        assert r.service_name == ""
        assert r.flag_category == FlagCategory.RELEASE
        assert r.impact_level == ImpactLevel.NONE_DETECTED
        assert r.reliability_delta_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_flag_analysis_defaults(self):
        r = FlagAnalysis()
        assert r.id
        assert r.analysis_name == ""
        assert r.flag_category == FlagCategory.RELEASE
        assert r.impact_type == ImpactType.NEUTRAL
        assert r.score == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_flag_impact_report_defaults(self):
        r = FlagImpactReport()
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.avg_reliability_delta_pct == 0.0
        assert r.by_category == {}
        assert r.by_impact_level == {}
        assert r.critical_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_impact
# -------------------------------------------------------------------


class TestRecordImpact:
    def test_basic(self):
        eng = _engine()
        r = eng.record_impact("auth-svc", flag_category=FlagCategory.RELEASE)
        assert r.service_name == "auth-svc"
        assert r.flag_category == FlagCategory.RELEASE

    def test_with_all_fields(self):
        eng = _engine()
        r = eng.record_impact(
            "api-gw",
            flag_category=FlagCategory.KILL_SWITCH,
            impact_level=ImpactLevel.CRITICAL,
            reliability_delta_pct=85.0,
            details="kill switch triggered",
        )
        assert r.impact_level == ImpactLevel.CRITICAL
        assert r.reliability_delta_pct == 85.0
        assert r.details == "kill switch triggered"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_impact(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_impact
# -------------------------------------------------------------------


class TestGetImpact:
    def test_found(self):
        eng = _engine()
        r = eng.record_impact("auth-svc")
        assert eng.get_impact(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_impact("nonexistent") is None


# -------------------------------------------------------------------
# list_impacts
# -------------------------------------------------------------------


class TestListImpacts:
    def test_list_all(self):
        eng = _engine()
        eng.record_impact("svc-a")
        eng.record_impact("svc-b")
        assert len(eng.list_impacts()) == 2

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_impact("svc-a")
        eng.record_impact("svc-b")
        results = eng.list_impacts(service_name="svc-a")
        assert len(results) == 1
        assert results[0].service_name == "svc-a"

    def test_filter_by_flag_category(self):
        eng = _engine()
        eng.record_impact("svc-a", flag_category=FlagCategory.RELEASE)
        eng.record_impact("svc-b", flag_category=FlagCategory.EXPERIMENT)
        results = eng.list_impacts(flag_category=FlagCategory.EXPERIMENT)
        assert len(results) == 1
        assert results[0].service_name == "svc-b"


# -------------------------------------------------------------------
# add_analysis
# -------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            "latency-check",
            flag_category=FlagCategory.OPERATIONAL,
            impact_type=ImpactType.LATENCY_INCREASE,
            score=7.5,
        )
        assert a.analysis_name == "latency-check"
        assert a.impact_type == ImpactType.LATENCY_INCREASE
        assert a.score == 7.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_analysis(f"analysis-{i}")
        assert len(eng._analyses) == 2


# -------------------------------------------------------------------
# analyze_flag_impact
# -------------------------------------------------------------------


class TestAnalyzeFlagImpact:
    def test_with_data(self):
        eng = _engine(min_reliability_pct=95.0)
        eng.record_impact("svc-a", reliability_delta_pct=97.0)
        eng.record_impact("svc-a", reliability_delta_pct=99.0)
        result = eng.analyze_flag_impact("svc-a")
        assert result["avg_reliability_delta_pct"] == 98.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_flag_impact("unknown-svc")
        assert result["status"] == "no_data"

    def test_below_threshold(self):
        eng = _engine(min_reliability_pct=95.0)
        eng.record_impact("svc-a", reliability_delta_pct=90.0)
        eng.record_impact("svc-a", reliability_delta_pct=88.0)
        result = eng.analyze_flag_impact("svc-a")
        assert result["meets_threshold"] is False


# -------------------------------------------------------------------
# identify_critical_flags
# -------------------------------------------------------------------


class TestIdentifyCriticalFlags:
    def test_with_critical(self):
        eng = _engine()
        eng.record_impact("svc-a", impact_level=ImpactLevel.CRITICAL)
        eng.record_impact("svc-a", impact_level=ImpactLevel.HIGH)
        eng.record_impact("svc-b", impact_level=ImpactLevel.LOW)
        results = eng.identify_critical_flags()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["critical_high_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_flags() == []

    def test_single_critical_not_returned(self):
        eng = _engine()
        eng.record_impact("svc-a", impact_level=ImpactLevel.CRITICAL)
        assert eng.identify_critical_flags() == []


# -------------------------------------------------------------------
# rank_by_reliability_delta
# -------------------------------------------------------------------


class TestRankByReliabilityDelta:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact("svc-a", reliability_delta_pct=90.0)
        eng.record_impact("svc-b", reliability_delta_pct=99.0)
        results = eng.rank_by_reliability_delta()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_reliability_delta_pct"] == 99.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_reliability_delta() == []


# -------------------------------------------------------------------
# detect_impact_trends
# -------------------------------------------------------------------


class TestDetectImpactTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_impact("svc-a")
        eng.record_impact("svc-b")
        results = eng.detect_impact_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["record_count"] == 5

    def test_empty(self):
        eng = _engine()
        assert eng.detect_impact_trends() == []

    def test_at_threshold_not_returned(self):
        eng = _engine()
        for _ in range(3):
            eng.record_impact("svc-a")
        assert eng.detect_impact_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact("svc-a", impact_level=ImpactLevel.CRITICAL, reliability_delta_pct=85.0)
        eng.record_impact("svc-b", impact_level=ImpactLevel.LOW, reliability_delta_pct=99.0)
        eng.add_analysis("check-1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_analyses == 1
        assert report.critical_count == 1
        assert report.by_category != {}
        assert report.by_impact_level != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert report.avg_reliability_delta_pct == 0.0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_impact("svc-a")
        eng.add_analysis("check-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine(min_reliability_pct=95.0)
        eng.record_impact("svc-a", flag_category=FlagCategory.RELEASE)
        eng.record_impact("svc-b", flag_category=FlagCategory.EXPERIMENT)
        eng.add_analysis("check-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_analyses"] == 1
        assert stats["unique_services"] == 2
        assert stats["min_reliability_pct"] == 95.0
