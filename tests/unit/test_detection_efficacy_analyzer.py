"""Tests for shieldops.security.detection_efficacy_analyzer — DetectionEfficacyAnalyzer."""

from __future__ import annotations

from shieldops.security.detection_efficacy_analyzer import (
    DetectionEfficacyAnalyzer,
    DetectionEfficacyReport,
    EfficacyAnalysis,
    EfficacyLevel,
    EfficacyMetric,
    EfficacyRecord,
    RuleSource,
)


def _engine(**kw) -> DetectionEfficacyAnalyzer:
    return DetectionEfficacyAnalyzer(**kw)


class TestEnums:
    def test_efficacy_metric_true_positive_rate(self):
        assert EfficacyMetric.TRUE_POSITIVE_RATE == "true_positive_rate"

    def test_efficacy_metric_false_positive_rate(self):
        assert EfficacyMetric.FALSE_POSITIVE_RATE == "false_positive_rate"

    def test_efficacy_metric_detection_latency(self):
        assert EfficacyMetric.DETECTION_LATENCY == "detection_latency"

    def test_efficacy_metric_coverage(self):
        assert EfficacyMetric.COVERAGE == "coverage"

    def test_efficacy_metric_precision(self):
        assert EfficacyMetric.PRECISION == "precision"

    def test_rule_source_sigma(self):
        assert RuleSource.SIGMA == "sigma"

    def test_rule_source_yara(self):
        assert RuleSource.YARA == "yara"

    def test_rule_source_custom(self):
        assert RuleSource.CUSTOM == "custom"

    def test_rule_source_vendor(self):
        assert RuleSource.VENDOR == "vendor"

    def test_rule_source_community(self):
        assert RuleSource.COMMUNITY == "community"

    def test_efficacy_level_excellent(self):
        assert EfficacyLevel.EXCELLENT == "excellent"

    def test_efficacy_level_good(self):
        assert EfficacyLevel.GOOD == "good"

    def test_efficacy_level_fair(self):
        assert EfficacyLevel.FAIR == "fair"

    def test_efficacy_level_poor(self):
        assert EfficacyLevel.POOR == "poor"

    def test_efficacy_level_ineffective(self):
        assert EfficacyLevel.INEFFECTIVE == "ineffective"


class TestModels:
    def test_record_defaults(self):
        r = EfficacyRecord()
        assert r.id
        assert r.name == ""
        assert r.efficacy_metric == EfficacyMetric.TRUE_POSITIVE_RATE
        assert r.rule_source == RuleSource.SIGMA
        assert r.efficacy_level == EfficacyLevel.INEFFECTIVE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = EfficacyAnalysis()
        assert a.id
        assert a.name == ""
        assert a.efficacy_metric == EfficacyMetric.TRUE_POSITIVE_RATE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = DetectionEfficacyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_efficacy_metric == {}
        assert r.by_rule_source == {}
        assert r.by_efficacy_level == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            efficacy_metric=EfficacyMetric.TRUE_POSITIVE_RATE,
            rule_source=RuleSource.YARA,
            efficacy_level=EfficacyLevel.EXCELLENT,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.efficacy_metric == EfficacyMetric.TRUE_POSITIVE_RATE
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_efficacy_metric(self):
        eng = _engine()
        eng.record_entry(name="a", efficacy_metric=EfficacyMetric.TRUE_POSITIVE_RATE)
        eng.record_entry(name="b", efficacy_metric=EfficacyMetric.FALSE_POSITIVE_RATE)
        assert len(eng.list_records(efficacy_metric=EfficacyMetric.TRUE_POSITIVE_RATE)) == 1

    def test_filter_by_rule_source(self):
        eng = _engine()
        eng.record_entry(name="a", rule_source=RuleSource.SIGMA)
        eng.record_entry(name="b", rule_source=RuleSource.YARA)
        assert len(eng.list_records(rule_source=RuleSource.SIGMA)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", efficacy_metric=EfficacyMetric.FALSE_POSITIVE_RATE, score=90.0)
        eng.record_entry(name="b", efficacy_metric=EfficacyMetric.FALSE_POSITIVE_RATE, score=70.0)
        result = eng.analyze_distribution()
        assert "false_positive_rate" in result
        assert result["false_positive_rate"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
