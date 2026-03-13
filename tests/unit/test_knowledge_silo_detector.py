"""Tests for KnowledgeSiloDetector."""

from __future__ import annotations

from shieldops.knowledge.knowledge_silo_detector import (
    ConcentrationType,
    KnowledgeArea,
    KnowledgeSiloDetector,
    SiloRisk,
)


def _engine(**kw) -> KnowledgeSiloDetector:
    return KnowledgeSiloDetector(**kw)


class TestEnums:
    def test_knowledge_area_values(self):
        for v in KnowledgeArea:
            assert isinstance(v.value, str)

    def test_silo_risk_values(self):
        for v in SiloRisk:
            assert isinstance(v.value, str)

    def test_concentration_type_values(self):
        for v in ConcentrationType:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(domain_id="d1")
        assert r.domain_id == "d1"

    def test_all_fields(self):
        eng = _engine()
        r = eng.add_record(
            domain_id="d1",
            person_id="p1",
            risk=SiloRisk.CRITICAL,
        )
        assert r.risk == SiloRisk.CRITICAL

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(domain_id=f"d-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(domain_id="d1", person_id="p1")
        a = eng.process(r.id)
        assert hasattr(a, "domain_id")
        assert a.bus_factor == 1

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(domain_id="d1")
        rpt = eng.generate_report()
        assert rpt.total_records > 0

    def test_empty(self):
        rpt = _engine().generate_report()
        assert rpt.total_records == 0


class TestGetStats:
    def test_has_total(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(domain_id="d1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(domain_id="d1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestIdentifyKnowledgeSilos:
    def test_single_person_silo(self):
        eng = _engine()
        eng.add_record(domain_id="d1", person_id="p1")
        result = eng.identify_knowledge_silos()
        assert len(result) == 1
        assert result[0]["severity"] == "critical"

    def test_empty(self):
        assert _engine().identify_knowledge_silos() == []


class TestComputeBusFactor:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(domain_id="d1", person_id="p1")
        eng.add_record(domain_id="d1", person_id="p2")
        result = eng.compute_bus_factor()
        assert len(result) == 1
        assert result[0]["bus_factor"] == 2

    def test_empty(self):
        assert _engine().compute_bus_factor() == []


class TestRankDomainsByConcentrationRisk:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(domain_id="d1", person_id="p1")
        eng.add_record(domain_id="d2", person_id="p1")
        eng.add_record(domain_id="d2", person_id="p2")
        result = eng.rank_domains_by_concentration_risk()
        assert len(result) == 2
        assert result[0]["rank"] == 1

    def test_empty(self):
        r = _engine()
        assert r.rank_domains_by_concentration_risk() == []
