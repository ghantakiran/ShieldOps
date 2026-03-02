"""Tests for shieldops.analytics.behavioral_baseline_engine — BehavioralBaselineEngine."""

from __future__ import annotations

from shieldops.analytics.behavioral_baseline_engine import (
    BaselineAnalysis,
    BaselineRecord,
    BaselineReport,
    BaselineStatus,
    BaselineType,
    BehavioralBaselineEngine,
    DeviationLevel,
)


def _engine(**kw) -> BehavioralBaselineEngine:
    return BehavioralBaselineEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_user_behavior(self):
        assert BaselineType.USER_BEHAVIOR == "user_behavior"

    def test_type_service_behavior(self):
        assert BaselineType.SERVICE_BEHAVIOR == "service_behavior"

    def test_type_network_traffic(self):
        assert BaselineType.NETWORK_TRAFFIC == "network_traffic"

    def test_type_api_usage(self):
        assert BaselineType.API_USAGE == "api_usage"

    def test_type_data_access(self):
        assert BaselineType.DATA_ACCESS == "data_access"

    def test_deviation_critical(self):
        assert DeviationLevel.CRITICAL == "critical"

    def test_deviation_significant(self):
        assert DeviationLevel.SIGNIFICANT == "significant"

    def test_deviation_moderate(self):
        assert DeviationLevel.MODERATE == "moderate"

    def test_deviation_minor(self):
        assert DeviationLevel.MINOR == "minor"

    def test_deviation_normal(self):
        assert DeviationLevel.NORMAL == "normal"

    def test_status_established(self):
        assert BaselineStatus.ESTABLISHED == "established"

    def test_status_learning(self):
        assert BaselineStatus.LEARNING == "learning"

    def test_status_updating(self):
        assert BaselineStatus.UPDATING == "updating"

    def test_status_stale(self):
        assert BaselineStatus.STALE == "stale"

    def test_status_invalid(self):
        assert BaselineStatus.INVALID == "invalid"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_baseline_record_defaults(self):
        r = BaselineRecord()
        assert r.id
        assert r.baseline_name == ""
        assert r.baseline_type == BaselineType.USER_BEHAVIOR
        assert r.deviation_level == DeviationLevel.CRITICAL
        assert r.baseline_status == BaselineStatus.ESTABLISHED
        assert r.deviation_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_baseline_analysis_defaults(self):
        c = BaselineAnalysis()
        assert c.id
        assert c.baseline_name == ""
        assert c.baseline_type == BaselineType.USER_BEHAVIOR
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_baseline_report_defaults(self):
        r = BaselineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_deviation_count == 0
        assert r.avg_deviation_score == 0.0
        assert r.by_type == {}
        assert r.by_deviation == {}
        assert r.by_status == {}
        assert r.top_high_deviation == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_baseline
# ---------------------------------------------------------------------------


class TestRecordBaseline:
    def test_basic(self):
        eng = _engine()
        r = eng.record_baseline(
            baseline_name="bl-001",
            baseline_type=BaselineType.SERVICE_BEHAVIOR,
            deviation_level=DeviationLevel.SIGNIFICANT,
            baseline_status=BaselineStatus.LEARNING,
            deviation_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.baseline_name == "bl-001"
        assert r.baseline_type == BaselineType.SERVICE_BEHAVIOR
        assert r.deviation_level == DeviationLevel.SIGNIFICANT
        assert r.baseline_status == BaselineStatus.LEARNING
        assert r.deviation_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_baseline(baseline_name=f"bl-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_baseline
# ---------------------------------------------------------------------------


class TestGetBaseline:
    def test_found(self):
        eng = _engine()
        r = eng.record_baseline(
            baseline_name="bl-001",
            deviation_level=DeviationLevel.CRITICAL,
        )
        result = eng.get_baseline(r.id)
        assert result is not None
        assert result.deviation_level == DeviationLevel.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_baseline("nonexistent") is None


# ---------------------------------------------------------------------------
# list_baselines
# ---------------------------------------------------------------------------


class TestListBaselines:
    def test_list_all(self):
        eng = _engine()
        eng.record_baseline(baseline_name="bl-001")
        eng.record_baseline(baseline_name="bl-002")
        assert len(eng.list_baselines()) == 2

    def test_filter_by_baseline_type(self):
        eng = _engine()
        eng.record_baseline(
            baseline_name="bl-001",
            baseline_type=BaselineType.USER_BEHAVIOR,
        )
        eng.record_baseline(
            baseline_name="bl-002",
            baseline_type=BaselineType.NETWORK_TRAFFIC,
        )
        results = eng.list_baselines(baseline_type=BaselineType.USER_BEHAVIOR)
        assert len(results) == 1

    def test_filter_by_deviation_level(self):
        eng = _engine()
        eng.record_baseline(
            baseline_name="bl-001",
            deviation_level=DeviationLevel.CRITICAL,
        )
        eng.record_baseline(
            baseline_name="bl-002",
            deviation_level=DeviationLevel.MINOR,
        )
        results = eng.list_baselines(deviation_level=DeviationLevel.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_baseline(baseline_name="bl-001", team="security")
        eng.record_baseline(baseline_name="bl-002", team="platform")
        results = eng.list_baselines(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_baseline(baseline_name=f"bl-{i}")
        assert len(eng.list_baselines(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            baseline_name="bl-001",
            baseline_type=BaselineType.SERVICE_BEHAVIOR,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="high deviation detected",
        )
        assert a.baseline_name == "bl-001"
        assert a.baseline_type == BaselineType.SERVICE_BEHAVIOR
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(baseline_name=f"bl-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_baseline_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_baseline(
            baseline_name="bl-001",
            baseline_type=BaselineType.USER_BEHAVIOR,
            deviation_score=90.0,
        )
        eng.record_baseline(
            baseline_name="bl-002",
            baseline_type=BaselineType.USER_BEHAVIOR,
            deviation_score=70.0,
        )
        result = eng.analyze_baseline_distribution()
        assert "user_behavior" in result
        assert result["user_behavior"]["count"] == 2
        assert result["user_behavior"]["avg_deviation_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_baseline_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_deviation_baselines
# ---------------------------------------------------------------------------


class TestIdentifyHighDeviationBaselines:
    def test_detects_above_threshold(self):
        eng = _engine(deviation_threshold=80.0)
        eng.record_baseline(baseline_name="bl-001", deviation_score=90.0)
        eng.record_baseline(baseline_name="bl-002", deviation_score=60.0)
        results = eng.identify_high_deviation_baselines()
        assert len(results) == 1
        assert results[0]["baseline_name"] == "bl-001"

    def test_sorted_descending(self):
        eng = _engine(deviation_threshold=50.0)
        eng.record_baseline(baseline_name="bl-001", deviation_score=80.0)
        eng.record_baseline(baseline_name="bl-002", deviation_score=95.0)
        results = eng.identify_high_deviation_baselines()
        assert len(results) == 2
        assert results[0]["deviation_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_deviation_baselines() == []


# ---------------------------------------------------------------------------
# rank_by_deviation
# ---------------------------------------------------------------------------


class TestRankByDeviation:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_baseline(baseline_name="bl-001", service="auth-svc", deviation_score=50.0)
        eng.record_baseline(baseline_name="bl-002", service="api-gw", deviation_score=90.0)
        results = eng.rank_by_deviation()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_deviation_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_deviation() == []


# ---------------------------------------------------------------------------
# detect_baseline_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(baseline_name="bl-001", analysis_score=50.0)
        result = eng.detect_baseline_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(baseline_name="bl-001", analysis_score=20.0)
        eng.add_analysis(baseline_name="bl-002", analysis_score=20.0)
        eng.add_analysis(baseline_name="bl-003", analysis_score=80.0)
        eng.add_analysis(baseline_name="bl-004", analysis_score=80.0)
        result = eng.detect_baseline_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_baseline_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(deviation_threshold=80.0)
        eng.record_baseline(
            baseline_name="bl-001",
            baseline_type=BaselineType.SERVICE_BEHAVIOR,
            deviation_level=DeviationLevel.SIGNIFICANT,
            baseline_status=BaselineStatus.LEARNING,
            deviation_score=95.0,
        )
        report = eng.generate_report()
        assert isinstance(report, BaselineReport)
        assert report.total_records == 1
        assert report.high_deviation_count == 1
        assert len(report.top_high_deviation) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_baseline(baseline_name="bl-001")
        eng.add_analysis(baseline_name="bl-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_baseline(
            baseline_name="bl-001",
            baseline_type=BaselineType.USER_BEHAVIOR,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "user_behavior" in stats["type_distribution"]
