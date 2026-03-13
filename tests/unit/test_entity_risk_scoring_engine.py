"""Tests for EntityRiskScoringEngine."""

from __future__ import annotations

from shieldops.security.entity_risk_scoring_engine import (
    EntityRiskScoringEngine,
    EntityType,
    RiskLevel,
    ScoringModel,
)


def _engine(**kw) -> EntityRiskScoringEngine:
    return EntityRiskScoringEngine(**kw)


class TestEnums:
    def test_entity_type_values(self):
        for v in EntityType:
            assert isinstance(v.value, str)

    def test_risk_level_values(self):
        for v in RiskLevel:
            assert isinstance(v.value, str)

    def test_scoring_model_values(self):
        for v in ScoringModel:
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
        r = eng.add_record(entity_id="e1", risk_score=90.0)
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
        rpt = eng.generate_report()
        assert rpt.total_records > 0

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


class TestComputeEntityRiskScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(entity_id="e1", risk_score=50.0)
        result = eng.compute_entity_risk_score()
        assert len(result) == 1
        assert result[0]["entity_id"] == "e1"

    def test_empty(self):
        assert _engine().compute_entity_risk_score() == []


class TestDetectRiskThresholdBreach:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            entity_id="e1",
            risk_score=90.0,
            threshold=80.0,
        )
        result = eng.detect_risk_threshold_breach()
        assert len(result) == 1
        assert result[0]["breach_amount"] == 10.0

    def test_empty(self):
        assert _engine().detect_risk_threshold_breach() == []


class TestRankEntitiesByRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(entity_id="e1", risk_score=50.0)
        eng.add_record(entity_id="e2", risk_score=80.0)
        result = eng.rank_entities_by_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_entities_by_risk() == []
