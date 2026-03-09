"""Tests for shieldops.analytics.operational_risk_intelligence — OperationalRiskIntelligence."""

from __future__ import annotations

from shieldops.analytics.operational_risk_intelligence import (
    MitigationStatus,
    OperationalRiskIntelligence,
    RiskDomain,
    RiskSeverity,
)


def _engine(**kw) -> OperationalRiskIntelligence:
    return OperationalRiskIntelligence(**kw)


class TestEnums:
    def test_risk_domain(self):
        assert RiskDomain.AVAILABILITY == "availability"

    def test_risk_severity(self):
        assert RiskSeverity.CRITICAL == "critical"

    def test_mitigation_status(self):
        assert MitigationStatus.MITIGATED == "mitigated"


class TestRecordItem:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_item(name="db-single-point", risk_domain=RiskDomain.AVAILABILITY)
        assert rec.name == "db-single-point"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"risk-{i}")
        assert len(eng._records) == 3


class TestRiskScores:
    def test_basic(self):
        eng = _engine()
        eng.record_item(
            name="r1", risk_severity=RiskSeverity.CRITICAL, likelihood_pct=80.0, impact_score=90.0
        )
        result = eng.calculate_risk_scores()
        assert isinstance(result, list)


class TestHeatMap:
    def test_basic(self):
        eng = _engine()
        eng.record_item(
            name="r1",
            risk_domain=RiskDomain.AVAILABILITY,
            risk_severity=RiskSeverity.HIGH,
            risk_score=60.0,
        )
        result = eng.generate_heat_map()
        assert isinstance(result, dict)


class TestMitigationProgress:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="r1", mitigation_status=MitigationStatus.IN_PROGRESS)
        result = eng.track_mitigation_progress()
        assert isinstance(result, dict)


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_item(name="r1")
        report = eng.generate_report()
        assert report.total_records >= 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestGetStats:
    def test_basic(self):
        eng = _engine()
        eng.record_item(name="r1")
        stats = eng.get_stats()
        assert stats["total_records"] >= 1


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="r1")
        eng.clear_data()
        assert eng.get_stats()["total_records"] == 0
