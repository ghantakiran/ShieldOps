"""Tests for RiskObservationEngine."""

from __future__ import annotations

from shieldops.security.risk_observation_engine import (
    ConsolidationStrategy,
    ObservationFidelity,
    ObservationType,
    RiskObservationEngine,
)


def _engine(**kw) -> RiskObservationEngine:
    return RiskObservationEngine(**kw)


class TestEnums:
    def test_observation_type_values(self):
        for v in ObservationType:
            assert isinstance(v.value, str)

    def test_observation_fidelity_values(self):
        for v in ObservationFidelity:
            assert isinstance(v.value, str)

    def test_consolidation_strategy_values(self):
        for v in ConsolidationStrategy:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(observation_id="o1")
        assert r.observation_id == "o1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(observation_id=f"o-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(observation_id="o1")
        a = eng.process(r.id)
        assert hasattr(a, "observation_id")
        assert a.observation_id == "o1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(observation_id="o1")
        assert eng.generate_report().total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(observation_id="o1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(observation_id="o1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestConsolidateObservations:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            observation_id="o1",
            entity_id="e1",
            risk_score=50.0,
        )
        result = eng.consolidate_observations()
        assert len(result) == 1
        assert result[0]["entity_id"] == "e1"

    def test_empty(self):
        assert _engine().consolidate_observations() == []


class TestComputeObservationDensity:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(observation_id="o1", entity_id="e1")
        eng.add_record(observation_id="o2", entity_id="e1")
        result = eng.compute_observation_density()
        assert len(result) == 1
        assert result[0]["density"] == 2

    def test_empty(self):
        assert _engine().compute_observation_density() == []


class TestDetectObservationPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            observation_id="o1",
            entity_id="e1",
            obs_type=ObservationType.ANOMALY,
        )
        eng.add_record(
            observation_id="o2",
            entity_id="e1",
            obs_type=ObservationType.POLICY_VIOLATION,
        )
        result = eng.detect_observation_patterns()
        assert len(result) == 1
        assert result[0]["diversity"] == 2

    def test_empty(self):
        assert _engine().detect_observation_patterns() == []
