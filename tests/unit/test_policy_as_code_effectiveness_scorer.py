"""Tests for PolicyAsCodeEffectivenessScorer."""

from __future__ import annotations

from shieldops.compliance.policy_as_code_effectiveness_scorer import (
    CoverageLevel,
    EnforcementMode,
    PolicyAsCodeEffectivenessScorer,
    PolicyLanguage,
)


def _engine(**kw) -> PolicyAsCodeEffectivenessScorer:
    return PolicyAsCodeEffectivenessScorer(**kw)


class TestEnums:
    def test_policy_language_values(self):
        for v in PolicyLanguage:
            assert isinstance(v.value, str)

    def test_coverage_level_values(self):
        for v in CoverageLevel:
            assert isinstance(v.value, str)

    def test_enforcement_mode_values(self):
        for v in EnforcementMode:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(policy_id="pol1")
        assert r.policy_id == "pol1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(policy_id=f"p-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            policy_id="pol1",
            effectiveness_score=85.0,
            violations_caught=8,
            violations_missed=2,
        )
        a = eng.process(r.id)
        assert hasattr(a, "policy_id")
        assert a.catch_rate == 0.8

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(policy_id="pol1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(policy_id="pol1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(policy_id="pol1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestScorePolicyCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            policy_id="pol1",
            effectiveness_score=90.0,
        )
        result = eng.score_policy_coverage()
        assert len(result) == 1
        assert result[0]["policy_id"] == "pol1"

    def test_empty(self):
        r = _engine().score_policy_coverage()
        assert r == []


class TestDetectPolicyBlindSpots:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            policy_id="pol1",
            violations_caught=5,
            violations_missed=3,
        )
        result = eng.detect_policy_blind_spots()
        assert len(result) == 1
        assert result[0]["violations_missed"] == 3

    def test_empty(self):
        r = _engine().detect_policy_blind_spots()
        assert r == []


class TestRankPoliciesByEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            policy_id="pol1",
            effectiveness_score=50.0,
        )
        eng.add_record(
            policy_id="pol2",
            effectiveness_score=80.0,
        )
        result = eng.rank_policies_by_enforcement_effectiveness()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine().rank_policies_by_enforcement_effectiveness()
        assert r == []
