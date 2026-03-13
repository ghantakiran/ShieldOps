"""Tests for EntityBehaviorRiskEngine."""

from __future__ import annotations

from shieldops.security.entity_behavior_risk_engine import (
    BehaviorBaseline,
    BehaviorCategory,
    EntityBehaviorRiskEngine,
    RiskContribution,
)


def _engine(**kw) -> EntityBehaviorRiskEngine:
    return EntityBehaviorRiskEngine(**kw)


class TestEnums:
    def test_behavior_category_values(self):
        for v in BehaviorCategory:
            assert isinstance(v.value, str)

    def test_behavior_baseline_values(self):
        for v in BehaviorBaseline:
            assert isinstance(v.value, str)

    def test_risk_contribution_values(self):
        for v in RiskContribution:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(entity_id="e1")
        assert r.entity_id == "e1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(entity_id=f"e-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            entity_id="e1",
            risk_score=50.0,
            baseline_score=40.0,
            deviation=10.0,
        )
        a = eng.process(r.id)
        assert hasattr(a, "entity_id")
        assert a.entity_id == "e1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(entity_id="e1")
        assert eng.generate_report().total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(entity_id="e1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(entity_id="e1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestScoreBehavioralRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(entity_id="e1", risk_score=60.0)
        result = eng.score_behavioral_risk()
        assert len(result) == 1
        assert result[0]["entity_id"] == "e1"

    def test_empty(self):
        assert _engine().score_behavioral_risk() == []


class TestDetectBaselineDeviation:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            entity_id="e1",
            baseline_score=50.0,
            deviation=20.0,
        )
        result = eng.detect_baseline_deviation()
        assert len(result) == 1
        assert result[0]["deviation_pct"] == 40.0

    def test_empty(self):
        assert _engine().detect_baseline_deviation() == []


class TestComputeBehaviorRiskVelocity:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(entity_id="e1", deviation=10.0)
        result = eng.compute_behavior_risk_velocity()
        assert len(result) == 1
        assert result[0]["velocity"] == 10.0

    def test_empty(self):
        assert _engine().compute_behavior_risk_velocity() == []
