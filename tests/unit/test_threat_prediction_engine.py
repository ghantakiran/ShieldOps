"""Tests for ThreatPredictionEngine."""

from __future__ import annotations

from shieldops.security.threat_prediction_engine import (
    PredictionConfidence,
    ThreatHorizon,
    ThreatPredictionEngine,
    ThreatVector,
)


def _engine(**kw) -> ThreatPredictionEngine:
    return ThreatPredictionEngine(**kw)


class TestEnums:
    def test_vector_network(self):
        assert ThreatVector.NETWORK == "network"

    def test_vector_endpoint(self):
        assert ThreatVector.ENDPOINT == "endpoint"

    def test_vector_identity(self):
        assert ThreatVector.IDENTITY == "identity"

    def test_vector_supply_chain(self):
        assert ThreatVector.SUPPLY_CHAIN == "supply_chain"

    def test_confidence_high(self):
        assert PredictionConfidence.HIGH == "high"

    def test_confidence_medium(self):
        assert PredictionConfidence.MEDIUM == "medium"

    def test_confidence_low(self):
        assert PredictionConfidence.LOW == "low"

    def test_confidence_uncertain(self):
        assert PredictionConfidence.UNCERTAIN == "uncertain"

    def test_horizon_imminent(self):
        assert ThreatHorizon.IMMINENT == "imminent"

    def test_horizon_short(self):
        assert ThreatHorizon.SHORT_TERM == "short_term"

    def test_horizon_medium(self):
        assert ThreatHorizon.MEDIUM_TERM == "medium_term"

    def test_horizon_long(self):
        assert ThreatHorizon.LONG_TERM == "long_term"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            threat_id="t1",
            threat_vector=ThreatVector.ENDPOINT,
            probability=0.8,
            velocity=5.0,
        )
        assert r.threat_id == "t1"
        assert r.probability == 0.8

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(threat_id=f"t-{i}")
        assert len(eng._records) == 3


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.add_record(threat_id="t1", probability=0.9, velocity=3.0)
        a = eng.process(r.id)
        assert a is not None
        assert a.threat_id == "t1"
        assert a.analysis_score > 0

    def test_missing_key(self):
        assert _engine().process("missing") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(threat_id="t1", probability=0.5)
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(threat_id="t1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(threat_id="t1")
        eng.process(eng._records[0].id)
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestPredictAttackProbability:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            threat_id="t1",
            threat_vector=ThreatVector.NETWORK,
            probability=0.9,
        )
        result = eng.predict_attack_probability()
        assert len(result) == 1
        assert result[0]["vector"] == "network"

    def test_empty(self):
        assert _engine().predict_attack_probability() == []


class TestIdentifyPrecursorPatterns:
    def test_basic(self):
        eng = _engine()
        eng.add_record(threat_id="t1", probability=0.3, velocity=5.0)
        result = eng.identify_precursor_patterns()
        assert len(result) == 1
        assert result[0]["precursor_score"] > 0

    def test_empty(self):
        assert _engine().identify_precursor_patterns() == []


class TestComputeThreatVelocity:
    def test_basic(self):
        eng = _engine()
        eng.add_record(threat_id="t1", velocity=10.0)
        result = eng.compute_threat_velocity()
        assert result["avg_velocity"] == 10.0

    def test_empty(self):
        result = _engine().compute_threat_velocity()
        assert result["avg_velocity"] == 0.0
