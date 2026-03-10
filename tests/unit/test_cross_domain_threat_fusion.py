"""Tests for CrossDomainThreatFusion."""

from __future__ import annotations

from shieldops.security.cross_domain_threat_fusion import (
    CrossDomainThreatFusion,
    FusionMethod,
    SecurityDomain,
    SignalFidelity,
)


def _engine(**kw) -> CrossDomainThreatFusion:
    return CrossDomainThreatFusion(**kw)


class TestEnums:
    def test_dom_endpoint(self):
        assert SecurityDomain.ENDPOINT == "endpoint"

    def test_dom_network(self):
        assert SecurityDomain.NETWORK == "network"

    def test_dom_cloud(self):
        assert SecurityDomain.CLOUD == "cloud"

    def test_dom_identity(self):
        assert SecurityDomain.IDENTITY == "identity"

    def test_method_correlation(self):
        assert FusionMethod.CORRELATION == "correlation"

    def test_method_enrichment(self):
        assert FusionMethod.ENRICHMENT == "enrichment"

    def test_method_aggregation(self):
        assert FusionMethod.AGGREGATION == "aggregation"

    def test_method_dedup(self):
        assert FusionMethod.DEDUP == "dedup"

    def test_fidelity_verified(self):
        assert SignalFidelity.VERIFIED == "verified"

    def test_fidelity_probable(self):
        assert SignalFidelity.PROBABLE == "probable"

    def test_fidelity_possible(self):
        assert SignalFidelity.POSSIBLE == "possible"

    def test_fidelity_noise(self):
        assert SignalFidelity.NOISE == "noise"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            signal_id="s1",
            domain=SecurityDomain.NETWORK,
            reliability_score=0.9,
        )
        assert r.signal_id == "s1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(signal_id=f"s-{i}")
        assert len(eng._records) == 3


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.add_record(
            signal_id="s1",
            reliability_score=0.8,
            correlated_signals=4,
        )
        a = eng.process(r.id)
        assert a is not None
        assert a.multi_stage_flag is True

    def test_missing_key(self):
        assert _engine().process("x") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(signal_id="s1")
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(signal_id="s1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(signal_id="s1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestFuseCrossDomainSignals:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            signal_id="s1",
            domain=SecurityDomain.CLOUD,
            reliability_score=0.9,
        )
        result = eng.fuse_cross_domain_signals()
        assert len(result) == 1
        assert result[0]["domain"] == "cloud"

    def test_empty(self):
        assert _engine().fuse_cross_domain_signals() == []


class TestDetectMultiStageAttacks:
    def test_basic(self):
        eng = _engine()
        eng.add_record(signal_id="s1", correlated_signals=5)
        result = eng.detect_multi_stage_attacks()
        assert len(result) == 1

    def test_below_threshold(self):
        eng = _engine()
        eng.add_record(signal_id="s1", correlated_signals=1)
        assert eng.detect_multi_stage_attacks() == []


class TestComputeSignalReliability:
    def test_basic(self):
        eng = _engine()
        eng.add_record(signal_id="s1", reliability_score=0.85)
        result = eng.compute_signal_reliability()
        assert result["overall_reliability"] == 0.85

    def test_empty(self):
        result = _engine().compute_signal_reliability()
        assert result["overall_reliability"] == 0.0
