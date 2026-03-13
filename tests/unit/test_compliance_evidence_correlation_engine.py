"""Tests for ComplianceEvidenceCorrelationEngine."""

from __future__ import annotations

from shieldops.audit.compliance_evidence_correlation_engine import (
    ComplianceEvidenceCorrelationEngine,
    CorrelationStrength,
    CorrelationType,
    EvidenceScope,
)


def _engine(**kw) -> ComplianceEvidenceCorrelationEngine:
    return ComplianceEvidenceCorrelationEngine(**kw)


class TestEnums:
    def test_correlation_type_values(self):
        for v in CorrelationType:
            assert isinstance(v.value, str)

    def test_evidence_scope_values(self):
        for v in EvidenceScope:
            assert isinstance(v.value, str)

    def test_correlation_strength_values(self):
        for v in CorrelationStrength:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(evidence_id="ev1")
        assert r.evidence_id == "ev1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(evidence_id=f"ev-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(evidence_id="ev1", reuse_count=5, control_count=3)
        a = eng.process(r.id)
        assert hasattr(a, "evidence_id")
        assert a.evidence_id == "ev1"

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(evidence_id="ev1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(evidence_id="ev1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(evidence_id="ev1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestComputeEvidenceReuseRatio:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(evidence_id="ev1", reuse_count=4, control_count=2)
        result = eng.compute_evidence_reuse_ratio()
        assert len(result) == 1
        assert result[0]["evidence_id"] == "ev1"

    def test_empty(self):
        assert _engine().compute_evidence_reuse_ratio() == []


class TestDetectRedundantCollections:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            evidence_id="ev1",
            correlation_type=CorrelationType.EXACT_MATCH,
            reuse_count=3,
            collection_cost=500.0,
        )
        result = eng.detect_redundant_collections()
        assert len(result) == 1
        assert result[0]["evidence_id"] == "ev1"

    def test_empty(self):
        assert _engine().detect_redundant_collections() == []


class TestRankEvidenceByCrossControlValue:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(evidence_id="ev1", control_count=5, reuse_count=3)
        eng.add_record(evidence_id="ev2", control_count=2, reuse_count=1)
        result = eng.rank_evidence_by_cross_control_value()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        assert _engine().rank_evidence_by_cross_control_value() == []
