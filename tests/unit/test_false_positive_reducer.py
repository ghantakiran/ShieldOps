"""Tests for shieldops.security.false_positive_reducer — FalsePositiveReducer."""

from __future__ import annotations

from shieldops.security.false_positive_reducer import (
    FalsePositiveReducer,
    FPAnalysis,
    FPCategory,
    FPRecord,
    FPReport,
    ReductionMethod,
    ReductionStatus,
)


def _engine(**kw) -> FalsePositiveReducer:
    return FalsePositiveReducer(**kw)


class TestEnums:
    def test_fpcategory_val1(self):
        assert FPCategory.MISCONFIGURATION == "misconfiguration"

    def test_fpcategory_val2(self):
        assert FPCategory.BENIGN_ACTIVITY == "benign_activity"

    def test_fpcategory_val3(self):
        assert FPCategory.KNOWN_BEHAVIOR == "known_behavior"

    def test_fpcategory_val4(self):
        assert FPCategory.TEST_TRAFFIC == "test_traffic"

    def test_fpcategory_val5(self):
        assert FPCategory.POLICY_EXCEPTION == "policy_exception"

    def test_reductionmethod_val1(self):
        assert ReductionMethod.WHITELIST == "whitelist"

    def test_reductionmethod_val2(self):
        assert ReductionMethod.THRESHOLD_ADJUST == "threshold_adjust"

    def test_reductionmethod_val3(self):
        assert ReductionMethod.PATTERN_EXCLUDE == "pattern_exclude"

    def test_reductionmethod_val4(self):
        assert ReductionMethod.CONTEXT_FILTER == "context_filter"

    def test_reductionmethod_val5(self):
        assert ReductionMethod.ML_SUPPRESS == "ml_suppress"

    def test_reductionstatus_val1(self):
        assert ReductionStatus.IDENTIFIED == "identified"

    def test_reductionstatus_val2(self):
        assert ReductionStatus.ANALYZED == "analyzed"

    def test_reductionstatus_val3(self):
        assert ReductionStatus.SUPPRESSED == "suppressed"

    def test_reductionstatus_val4(self):
        assert ReductionStatus.VERIFIED == "verified"

    def test_reductionstatus_val5(self):
        assert ReductionStatus.REVERTED == "reverted"


class TestModels:
    def test_record_defaults(self):
        r = FPRecord()
        assert r.id
        assert r.rule_name == ""

    def test_analysis_defaults(self):
        a = FPAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = FPReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_fp(
            rule_name="test",
            fp_category=FPCategory.BENIGN_ACTIVITY,
            fp_rate=92.0,
            service="auth",
            team="sec",
        )
        assert r.rule_name == "test"
        assert r.fp_rate == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_fp(rule_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_fp(rule_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_fp(rule_name="a")
        eng.record_fp(rule_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_fp(rule_name="a", fp_category=FPCategory.MISCONFIGURATION)
        eng.record_fp(rule_name="b", fp_category=FPCategory.BENIGN_ACTIVITY)
        assert len(eng.list_records(fp_category=FPCategory.MISCONFIGURATION)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_fp(rule_name="a", reduction_method=ReductionMethod.WHITELIST)
        eng.record_fp(rule_name="b", reduction_method=ReductionMethod.THRESHOLD_ADJUST)
        assert len(eng.list_records(reduction_method=ReductionMethod.WHITELIST)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_fp(rule_name="a", team="sec")
        eng.record_fp(rule_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_fp(rule_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            rule_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(rule_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_fp(rule_name="a", fp_category=FPCategory.MISCONFIGURATION, fp_rate=90.0)
        eng.record_fp(rule_name="b", fp_category=FPCategory.MISCONFIGURATION, fp_rate=70.0)
        result = eng.analyze_distribution()
        assert FPCategory.MISCONFIGURATION.value in result
        assert result[FPCategory.MISCONFIGURATION.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_fp(rule_name="a", fp_rate=60.0)
        eng.record_fp(rule_name="b", fp_rate=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_fp(rule_name="a", fp_rate=50.0)
        eng.record_fp(rule_name="b", fp_rate=30.0)
        results = eng.identify_gaps()
        assert results[0]["fp_rate"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_fp(rule_name="a", service="auth", fp_rate=90.0)
        eng.record_fp(rule_name="b", service="api", fp_rate=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(rule_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(rule_name="a", analysis_score=20.0)
        eng.add_analysis(rule_name="b", analysis_score=20.0)
        eng.add_analysis(rule_name="c", analysis_score=80.0)
        eng.add_analysis(rule_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_fp(rule_name="test", fp_rate=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_fp(rule_name="test")
        eng.add_analysis(rule_name="test")
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
        eng.record_fp(rule_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
