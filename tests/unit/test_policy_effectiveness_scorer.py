"""Tests for PolicyEffectivenessScorer."""

from __future__ import annotations

from shieldops.compliance.policy_effectiveness_scorer import (
    EffectivenessRating,
    PolicyEffectivenessScorer,
    PolicyType,
    ViolationTrend,
)


def _engine(**kw) -> PolicyEffectivenessScorer:
    return PolicyEffectivenessScorer(**kw)


class TestEnums:
    def test_effectiveness_rating_values(self):
        for v in EffectivenessRating:
            assert isinstance(v.value, str)

    def test_policy_type_values(self):
        for v in PolicyType:
            assert isinstance(v.value, str)

    def test_violation_trend_values(self):
        for v in ViolationTrend:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(policy_id="p1")
        assert r.policy_id == "p1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(policy_id=f"p-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(policy_id="p1", effectiveness_score=85.0)
        a = eng.process(r.id)
        assert hasattr(a, "policy_id")
        assert a.policy_id == "p1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(policy_id="p1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(policy_id="p1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(policy_id="p1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputePolicyEffectivenessScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(policy_id="p1", effectiveness_score=75.0)
        result = eng.compute_policy_effectiveness_score()
        assert len(result) == 1
        assert result[0]["policy_id"] == "p1"

    def test_empty(self):
        assert _engine().compute_policy_effectiveness_score() == []


class TestDetectIneffectivePolicies:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            policy_id="p1",
            effectiveness_rating=EffectivenessRating.INEFFECTIVE,
            violation_count=15,
        )
        result = eng.detect_ineffective_policies()
        assert len(result) == 1
        assert result[0]["policy_id"] == "p1"

    def test_empty(self):
        assert _engine().detect_ineffective_policies() == []


class TestRankPoliciesByViolationTrend:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(policy_id="p1", violation_count=20)
        eng.add_record(policy_id="p2", violation_count=5)
        result = eng.rank_policies_by_violation_trend()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_policies_by_violation_trend() == []
