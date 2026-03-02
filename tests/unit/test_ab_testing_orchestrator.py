"""Tests for shieldops.analytics.ab_testing_orchestrator — ABTestingOrchestrator."""

from __future__ import annotations

from shieldops.analytics.ab_testing_orchestrator import (
    ABTestAnalysis,
    ABTestingOrchestrator,
    ABTestRecord,
    ABTestReport,
    SignificanceLevel,
    TestStatus,
    TestVariant,
)


def _engine(**kw) -> ABTestingOrchestrator:
    return ABTestingOrchestrator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_variant_control(self):
        assert TestVariant.CONTROL == "control"

    def test_variant_treatment_a(self):
        assert TestVariant.TREATMENT_A == "treatment_a"

    def test_variant_treatment_b(self):
        assert TestVariant.TREATMENT_B == "treatment_b"

    def test_variant_treatment_c(self):
        assert TestVariant.TREATMENT_C == "treatment_c"

    def test_variant_holdout(self):
        assert TestVariant.HOLDOUT == "holdout"

    def test_status_running(self):
        assert TestStatus.RUNNING == "running"

    def test_status_completed(self):
        assert TestStatus.COMPLETED == "completed"

    def test_status_stopped(self):
        assert TestStatus.STOPPED == "stopped"

    def test_status_failed(self):
        assert TestStatus.FAILED == "failed"

    def test_status_pending(self):
        assert TestStatus.PENDING == "pending"

    def test_sig_p001(self):
        assert SignificanceLevel.P_001 == "p_001"

    def test_sig_p005(self):
        assert SignificanceLevel.P_005 == "p_005"

    def test_sig_p01(self):
        assert SignificanceLevel.P_01 == "p_01"

    def test_sig_p05(self):
        assert SignificanceLevel.P_05 == "p_05"

    def test_sig_not_significant(self):
        assert SignificanceLevel.NOT_SIGNIFICANT == "not_significant"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_ab_test_record_defaults(self):
        r = ABTestRecord()
        assert r.id
        assert r.test_id == ""
        assert r.model_id == ""
        assert r.test_variant == TestVariant.CONTROL
        assert r.test_status == TestStatus.PENDING
        assert r.significance_level == SignificanceLevel.NOT_SIGNIFICANT
        assert r.effect_size == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_ab_test_analysis_defaults(self):
        a = ABTestAnalysis()
        assert a.id
        assert a.test_id == ""
        assert a.test_variant == TestVariant.CONTROL
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_ab_test_report_defaults(self):
        r = ABTestReport()
        assert r.id
        assert r.total_records == 0
        assert r.significant_count == 0
        assert r.avg_effect_size == 0.0
        assert r.by_variant == {}
        assert r.by_status == {}
        assert r.by_significance == {}
        assert r.top_winners == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_init(self):
        eng = _engine()
        assert eng._max_records == 200000
        assert eng._min_effect_size == 0.05

    def test_custom_init(self):
        eng = _engine(max_records=500, min_effect_size=0.1)
        assert eng._max_records == 500
        assert eng._min_effect_size == 0.1

    def test_empty_stats(self):
        eng = _engine()
        assert eng.get_stats()["total_records"] == 0


# ---------------------------------------------------------------------------
# record_test / get_test
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_test(
            test_id="test-001",
            model_id="model-001",
            test_variant=TestVariant.TREATMENT_A,
            test_status=TestStatus.RUNNING,
            significance_level=SignificanceLevel.P_005,
            effect_size=0.12,
            service="ab-svc",
            team="ml-team",
        )
        assert r.test_id == "test-001"
        assert r.test_variant == TestVariant.TREATMENT_A
        assert r.effect_size == 0.12

    def test_get_found(self):
        eng = _engine()
        r = eng.record_test(test_id="t-001", effect_size=0.08)
        assert eng.get_test(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_test("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_test(test_id=f"t-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_tests
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_test(test_id="t-001")
        eng.record_test(test_id="t-002")
        assert len(eng.list_tests()) == 2

    def test_filter_by_variant(self):
        eng = _engine()
        eng.record_test(test_id="t-001", test_variant=TestVariant.CONTROL)
        eng.record_test(test_id="t-002", test_variant=TestVariant.TREATMENT_A)
        assert len(eng.list_tests(test_variant=TestVariant.CONTROL)) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_test(test_id="t-001", test_status=TestStatus.RUNNING)
        eng.record_test(test_id="t-002", test_status=TestStatus.COMPLETED)
        assert len(eng.list_tests(test_status=TestStatus.RUNNING)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_test(test_id="t-001", team="ml-team")
        eng.record_test(test_id="t-002", team="data-team")
        assert len(eng.list_tests(team="ml-team")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_test(test_id=f"t-{i}")
        assert len(eng.list_tests(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic_analysis(self):
        eng = _engine()
        a = eng.add_analysis(
            test_id="t-001",
            test_variant=TestVariant.TREATMENT_A,
            analysis_score=0.15,
            threshold=0.05,
            breached=True,
            description="significant effect",
        )
        assert a.test_id == "t-001"
        assert a.analysis_score == 0.15
        assert a.breached is True

    def test_analysis_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(test_id=f"t-{i}")
        assert len(eng._analyses) == 2

    def test_analysis_defaults(self):
        eng = _engine()
        a = eng.add_analysis(test_id="t-test")
        assert a.test_variant == TestVariant.CONTROL
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_test(test_id="t-001", test_variant=TestVariant.CONTROL, effect_size=0.05)
        eng.record_test(test_id="t-002", test_variant=TestVariant.CONTROL, effect_size=0.1)
        result = eng.analyze_distribution()
        assert "control" in result
        assert result["control"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_severe_drifts
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_above_threshold(self):
        eng = _engine(min_effect_size=0.05)
        eng.record_test(test_id="t-001", effect_size=0.15)
        eng.record_test(test_id="t-002", effect_size=0.02)
        results = eng.identify_severe_drifts()
        assert len(results) == 1
        assert results[0]["test_id"] == "t-001"

    def test_sorted_descending(self):
        eng = _engine(min_effect_size=0.05)
        eng.record_test(test_id="t-001", effect_size=0.1)
        eng.record_test(test_id="t-002", effect_size=0.3)
        results = eng.identify_severe_drifts()
        assert results[0]["effect_size"] == 0.3

    def test_empty(self):
        eng = _engine()
        assert eng.identify_severe_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_test(test_id="t-001", effect_size=0.05)
        eng.record_test(test_id="t-002", effect_size=0.5)
        results = eng.rank_by_severity()
        assert results[0]["test_id"] == "t-002"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_severity() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(test_id="t-001", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(test_id="t-001", analysis_score=20.0)
        eng.add_analysis(test_id="t-002", analysis_score=20.0)
        eng.add_analysis(test_id="t-003", analysis_score=80.0)
        eng.add_analysis(test_id="t-004", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(min_effect_size=0.05)
        eng.record_test(
            test_id="t-001",
            test_variant=TestVariant.TREATMENT_A,
            test_status=TestStatus.COMPLETED,
            significance_level=SignificanceLevel.P_005,
            effect_size=0.15,
        )
        report = eng.generate_report()
        assert isinstance(report, ABTestReport)
        assert report.total_records == 1
        assert report.significant_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert len(report.recommendations) > 0


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_test(test_id="t-001")
        eng.add_analysis(test_id="t-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["variant_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_test(test_id="t-001", test_variant=TestVariant.CONTROL, team="ml-team")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_tests"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_record_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_test(test_id=f"t-{i}")
        assert len(eng._records) == 3
        assert eng._records[0].test_id == "t-2"
