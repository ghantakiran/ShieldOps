"""Tests for shieldops.security.adversarial_robustness_tester."""

from __future__ import annotations

from shieldops.security.adversarial_robustness_tester import (
    AdversarialRobustnessTester,
    AttackType,
    RobustnessAnalysis,
    RobustnessLevel,
    RobustnessRecord,
    RobustnessReport,
    TestStrategy,
)


def _engine(**kw) -> AdversarialRobustnessTester:
    return AdversarialRobustnessTester(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_attack_evasion(self):
        assert AttackType.EVASION == "evasion"

    def test_attack_poisoning(self):
        assert AttackType.POISONING == "poisoning"

    def test_attack_model_extraction(self):
        assert AttackType.MODEL_EXTRACTION == "model_extraction"

    def test_attack_inference(self):
        assert AttackType.INFERENCE == "inference"

    def test_attack_backdoor(self):
        assert AttackType.BACKDOOR == "backdoor"

    def test_level_robust(self):
        assert RobustnessLevel.ROBUST == "robust"

    def test_level_mostly_robust(self):
        assert RobustnessLevel.MOSTLY_ROBUST == "mostly_robust"

    def test_level_vulnerable(self):
        assert RobustnessLevel.VULNERABLE == "vulnerable"

    def test_level_highly_vulnerable(self):
        assert RobustnessLevel.HIGHLY_VULNERABLE == "highly_vulnerable"

    def test_level_unknown(self):
        assert RobustnessLevel.UNKNOWN == "unknown"

    def test_strategy_white_box(self):
        assert TestStrategy.WHITE_BOX == "white_box"

    def test_strategy_black_box(self):
        assert TestStrategy.BLACK_BOX == "black_box"

    def test_strategy_grey_box(self):
        assert TestStrategy.GREY_BOX == "grey_box"

    def test_strategy_adaptive(self):
        assert TestStrategy.ADAPTIVE == "adaptive"

    def test_strategy_transfer(self):
        assert TestStrategy.TRANSFER == "transfer"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_robustness_record_defaults(self):
        r = RobustnessRecord()
        assert r.id
        assert r.model_id == ""
        assert r.attack_type == AttackType.EVASION
        assert r.robustness_level == RobustnessLevel.UNKNOWN
        assert r.test_strategy == TestStrategy.BLACK_BOX
        assert r.robustness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_robustness_analysis_defaults(self):
        a = RobustnessAnalysis()
        assert a.id
        assert a.model_id == ""
        assert a.attack_type == AttackType.EVASION
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_robustness_report_defaults(self):
        r = RobustnessReport()
        assert r.id
        assert r.total_records == 0
        assert r.vulnerable_count == 0
        assert r.avg_robustness_score == 0.0
        assert r.by_attack == {}
        assert r.by_level == {}
        assert r.by_strategy == {}
        assert r.top_vulnerable == []
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
        assert eng._robustness_threshold == 0.7

    def test_custom_init(self):
        eng = _engine(max_records=500, robustness_threshold=0.8)
        assert eng._max_records == 500
        assert eng._robustness_threshold == 0.8

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
            model_id="model-001",
            attack_type=AttackType.POISONING,
            robustness_level=RobustnessLevel.VULNERABLE,
            test_strategy=TestStrategy.WHITE_BOX,
            robustness_score=0.45,
            service="ml-svc",
            team="red-team",
        )
        assert r.model_id == "model-001"
        assert r.attack_type == AttackType.POISONING
        assert r.robustness_score == 0.45

    def test_get_found(self):
        eng = _engine()
        r = eng.record_test(model_id="m-001", robustness_score=0.8)
        assert eng.get_test(r.id) is not None

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_test("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_test(model_id=f"m-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_tests
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_test(model_id="m-001")
        eng.record_test(model_id="m-002")
        assert len(eng.list_tests()) == 2

    def test_filter_by_attack_type(self):
        eng = _engine()
        eng.record_test(model_id="m-001", attack_type=AttackType.EVASION)
        eng.record_test(model_id="m-002", attack_type=AttackType.BACKDOOR)
        assert len(eng.list_tests(attack_type=AttackType.EVASION)) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_test(model_id="m-001", robustness_level=RobustnessLevel.ROBUST)
        eng.record_test(model_id="m-002", robustness_level=RobustnessLevel.VULNERABLE)
        assert len(eng.list_tests(robustness_level=RobustnessLevel.ROBUST)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_test(model_id="m-001", team="red-team")
        eng.record_test(model_id="m-002", team="blue-team")
        assert len(eng.list_tests(team="red-team")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_test(model_id=f"m-{i}")
        assert len(eng.list_tests(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic_analysis(self):
        eng = _engine()
        a = eng.add_analysis(
            model_id="m-001",
            attack_type=AttackType.EVASION,
            analysis_score=55.0,
            threshold=70.0,
            breached=True,
            description="evasion attack succeeded",
        )
        assert a.model_id == "m-001"
        assert a.analysis_score == 55.0
        assert a.breached is True

    def test_analysis_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(model_id=f"m-{i}")
        assert len(eng._analyses) == 2

    def test_analysis_defaults(self):
        eng = _engine()
        a = eng.add_analysis(model_id="m-test")
        assert a.attack_type == AttackType.EVASION
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_test(model_id="m-001", attack_type=AttackType.EVASION, robustness_score=0.8)
        eng.record_test(model_id="m-002", attack_type=AttackType.EVASION, robustness_score=0.6)
        result = eng.analyze_distribution()
        assert "evasion" in result
        assert result["evasion"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_severe_drifts
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(robustness_threshold=0.7)
        eng.record_test(model_id="m-001", robustness_score=0.5)
        eng.record_test(model_id="m-002", robustness_score=0.9)
        results = eng.identify_severe_drifts()
        assert len(results) == 1
        assert results[0]["model_id"] == "m-001"

    def test_sorted_ascending(self):
        eng = _engine(robustness_threshold=0.7)
        eng.record_test(model_id="m-001", robustness_score=0.6)
        eng.record_test(model_id="m-002", robustness_score=0.4)
        results = eng.identify_severe_drifts()
        assert results[0]["robustness_score"] == 0.4

    def test_empty(self):
        eng = _engine()
        assert eng.identify_severe_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_test(model_id="m-001", robustness_score=0.9)
        eng.record_test(model_id="m-002", robustness_score=0.4)
        results = eng.rank_by_severity()
        assert results[0]["model_id"] == "m-002"

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
            eng.add_analysis(model_id="m-001", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(model_id="m-001", analysis_score=20.0)
        eng.add_analysis(model_id="m-002", analysis_score=20.0)
        eng.add_analysis(model_id="m-003", analysis_score=80.0)
        eng.add_analysis(model_id="m-004", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(robustness_threshold=0.7)
        eng.record_test(
            model_id="m-001",
            attack_type=AttackType.EVASION,
            robustness_level=RobustnessLevel.VULNERABLE,
            test_strategy=TestStrategy.BLACK_BOX,
            robustness_score=0.4,
        )
        report = eng.generate_report()
        assert isinstance(report, RobustnessReport)
        assert report.total_records == 1
        assert report.vulnerable_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_test(model_id="m-001")
        eng.add_analysis(model_id="m-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["attack_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_test(model_id="m-001", attack_type=AttackType.EVASION, team="red-team")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_record_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_test(model_id=f"m-{i}")
        assert len(eng._records) == 3
        assert eng._records[0].model_id == "m-2"
