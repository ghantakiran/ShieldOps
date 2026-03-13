"""Tests for EvidenceChainIntegrityEngine."""

from __future__ import annotations

from shieldops.compliance.evidence_chain_integrity_engine import (
    ChainType,
    EvidenceChainIntegrityEngine,
    IntegrityRisk,
    IntegrityStatus,
)


def _engine(**kw) -> EvidenceChainIntegrityEngine:
    return EvidenceChainIntegrityEngine(**kw)


class TestEnums:
    def test_integrity_status_values(self):
        for v in IntegrityStatus:
            assert isinstance(v.value, str)

    def test_chain_type_values(self):
        for v in ChainType:
            assert isinstance(v.value, str)

    def test_integrity_risk_values(self):
        for v in IntegrityRisk:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(chain_id="ch1")
        assert r.chain_id == "ch1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(chain_id=f"ch-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(chain_id="ch1", integrity_score=95.0)
        a = eng.process(r.id)
        assert hasattr(a, "chain_id")
        assert a.chain_id == "ch1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(chain_id="ch1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(chain_id="ch1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(chain_id="ch1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeChainIntegrityScore:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(chain_id="ch1", integrity_score=90.0)
        result = eng.compute_chain_integrity_score()
        assert len(result) == 1
        assert result[0]["chain_id"] == "ch1"

    def test_empty(self):
        assert _engine().compute_chain_integrity_score() == []


class TestDetectBrokenEvidenceChains:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            chain_id="ch1",
            integrity_status=IntegrityStatus.BROKEN,
            integrity_score=20.0,
        )
        result = eng.detect_broken_evidence_chains()
        assert len(result) == 1
        assert result[0]["chain_id"] == "ch1"

    def test_empty(self):
        assert _engine().detect_broken_evidence_chains() == []


class TestRankEvidenceByIntegrityRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(evidence_id="ev1", integrity_score=40.0)
        eng.add_record(evidence_id="ev2", integrity_score=80.0)
        result = eng.rank_evidence_by_integrity_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_evidence_by_integrity_risk() == []
