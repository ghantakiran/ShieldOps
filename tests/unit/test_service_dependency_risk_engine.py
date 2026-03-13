"""Tests for ServiceDependencyRiskEngine."""

from __future__ import annotations

from shieldops.topology.service_dependency_risk_engine import (
    CouplingStrength,
    FailureDomain,
    RiskLevel,
    ServiceDependencyRiskEngine,
)


def _engine(**kw) -> ServiceDependencyRiskEngine:
    return ServiceDependencyRiskEngine(**kw)


class TestEnums:
    def test_risk_level_values(self):
        for v in RiskLevel:
            assert isinstance(v.value, str)

    def test_coupling_strength_values(self):
        for v in CouplingStrength:
            assert isinstance(v.value, str)

    def test_failure_domain_values(self):
        for v in FailureDomain:
            assert isinstance(v.value, str)


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(source_service="svc-a")
        assert r.source_service == "svc-a"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.record_item(source_service=f"svc-{i}")
        assert len(eng._records) == 5

    def test_all_fields(self):
        eng = _engine()
        r = eng.record_item(
            source_service="svc-a",
            target_service="svc-b",
            risk_level=RiskLevel.HIGH,
            coupling_strength=CouplingStrength.TIGHT,
            risk_score=85.0,
        )
        assert r.risk_level == RiskLevel.HIGH


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(
            source_service="svc-a",
            risk_score=70.0,
        )
        a = eng.process(r.id)
        assert a.computed_risk == 70.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(source_service="svc-a")
        rpt = eng.generate_report()
        assert rpt.total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_high_risk(self):
        eng = _engine()
        eng.record_item(
            source_service="svc-a",
            target_service="svc-b",
            risk_level=RiskLevel.CRITICAL,
        )
        rpt = eng.generate_report()
        assert len(rpt.high_risk_deps) == 1


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.record_item(source_service="svc-a")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.record_item(source_service="svc-a")
        eng.clear_data()
        assert len(eng._records) == 0


class TestQuantifyDependencyRisk:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            source_service="a",
            target_service="b",
            risk_score=50.0,
        )
        result = eng.quantify_dependency_risk()
        assert len(result) == 1

    def test_empty(self):
        assert _engine().quantify_dependency_risk() == []


class TestDetectSharedFailureDomains:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            source_service="svc-a",
            failure_domain=FailureDomain.REGION,
        )
        eng.record_item(
            source_service="svc-b",
            failure_domain=FailureDomain.REGION,
        )
        result = eng.detect_shared_failure_domains()
        assert len(result) == 1
        assert result[0]["service_count"] == 2

    def test_empty(self):
        assert _engine().detect_shared_failure_domains() == []


class TestRecommendDependencyDecoupling:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            source_service="a",
            target_service="b",
            coupling_strength=CouplingStrength.TIGHT,
            risk_score=80.0,
        )
        result = eng.recommend_dependency_decoupling()
        assert len(result) == 1
        assert "async" in result[0]["recommendation"].lower()

    def test_empty(self):
        assert _engine().recommend_dependency_decoupling() == []
