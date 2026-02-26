"""Tests for shieldops.topology.dependency_risk — DependencyRiskScorer."""

from __future__ import annotations

from shieldops.topology.dependency_risk import (
    DependencyRiskRecord,
    DependencyRiskReport,
    DependencyRiskScorer,
    MitigationStatus,
    RiskFactor,
    RiskMitigation,
    RiskTier,
)


def _engine(**kw) -> DependencyRiskScorer:
    return DependencyRiskScorer(**kw)


class TestEnums:
    def test_factor_version_lag(self):
        assert RiskFactor.VERSION_LAG == "version_lag"

    def test_factor_single_maintainer(self):
        assert RiskFactor.SINGLE_MAINTAINER == "single_maintainer"

    def test_factor_no_fallback(self):
        assert RiskFactor.NO_FALLBACK == "no_fallback"

    def test_factor_high_blast(self):
        assert RiskFactor.HIGH_BLAST_RADIUS == "high_blast_radius"

    def test_factor_transitive(self):
        assert RiskFactor.TRANSITIVE_DEPTH == "transitive_depth"

    def test_tier_critical(self):
        assert RiskTier.CRITICAL == "critical"

    def test_tier_high(self):
        assert RiskTier.HIGH == "high"

    def test_tier_moderate(self):
        assert RiskTier.MODERATE == "moderate"

    def test_tier_low(self):
        assert RiskTier.LOW == "low"

    def test_tier_acceptable(self):
        assert RiskTier.ACCEPTABLE == "acceptable"

    def test_mit_unmitigated(self):
        assert MitigationStatus.UNMITIGATED == "unmitigated"

    def test_mit_in_progress(self):
        assert MitigationStatus.IN_PROGRESS == "in_progress"

    def test_mit_partially(self):
        assert MitigationStatus.PARTIALLY_MITIGATED == "partially_mitigated"

    def test_mit_fully(self):
        assert MitigationStatus.FULLY_MITIGATED == "fully_mitigated"

    def test_mit_accepted(self):
        assert MitigationStatus.ACCEPTED == "accepted"


class TestModels:
    def test_risk_record_defaults(self):
        r = DependencyRiskRecord()
        assert r.id
        assert r.dependency_name == ""
        assert r.risk_factor == RiskFactor.VERSION_LAG
        assert r.risk_tier == RiskTier.MODERATE
        assert r.risk_score == 0.0
        assert r.mitigation_status == MitigationStatus.UNMITIGATED
        assert r.affected_services_count == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_mitigation_defaults(self):
        r = RiskMitigation()
        assert r.id
        assert r.dependency_name == ""
        assert r.mitigation_name == ""
        assert r.status == MitigationStatus.IN_PROGRESS
        assert r.effectiveness_pct == 0.0
        assert r.notes == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = DependencyRiskReport()
        assert r.total_risks == 0
        assert r.total_mitigations == 0
        assert r.avg_risk_score == 0.0
        assert r.by_risk_factor == {}
        assert r.by_tier == {}
        assert r.critical_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordRisk:
    def test_basic(self):
        eng = _engine()
        r = eng.record_risk("dep-a", risk_score=95.0)
        assert r.dependency_name == "dep-a"
        assert r.risk_tier == RiskTier.CRITICAL

    def test_auto_tier_high(self):
        eng = _engine()
        r = eng.record_risk("dep-b", risk_score=75.0)
        assert r.risk_tier == RiskTier.HIGH

    def test_auto_tier_acceptable(self):
        eng = _engine()
        r = eng.record_risk("dep-c", risk_score=10.0)
        assert r.risk_tier == RiskTier.ACCEPTABLE

    def test_explicit_tier(self):
        eng = _engine()
        r = eng.record_risk("dep-d", risk_tier=RiskTier.LOW)
        assert r.risk_tier == RiskTier.LOW

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_risk(f"dep-{i}")
        assert len(eng._records) == 3


class TestGetRisk:
    def test_found(self):
        eng = _engine()
        r = eng.record_risk("dep-a")
        assert eng.get_risk(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_risk("nonexistent") is None


class TestListRisks:
    def test_list_all(self):
        eng = _engine()
        eng.record_risk("dep-a")
        eng.record_risk("dep-b")
        assert len(eng.list_risks()) == 2

    def test_filter_by_dependency(self):
        eng = _engine()
        eng.record_risk("dep-a")
        eng.record_risk("dep-b")
        results = eng.list_risks(dependency_name="dep-a")
        assert len(results) == 1

    def test_filter_by_factor(self):
        eng = _engine()
        eng.record_risk("dep-a", risk_factor=RiskFactor.NO_FALLBACK)
        eng.record_risk("dep-b", risk_factor=RiskFactor.VERSION_LAG)
        results = eng.list_risks(risk_factor=RiskFactor.NO_FALLBACK)
        assert len(results) == 1


class TestRecordMitigation:
    def test_basic(self):
        eng = _engine()
        m = eng.record_mitigation("dep-a", "add-fallback", effectiveness_pct=80.0)
        assert m.mitigation_name == "add-fallback"
        assert m.effectiveness_pct == 80.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_mitigation(f"dep-{i}", f"mit-{i}")
        assert len(eng._mitigations) == 2


class TestAnalyzeDependencyRisk:
    def test_with_data(self):
        eng = _engine()
        eng.record_risk("dep-a", risk_score=85.0)
        result = eng.analyze_dependency_risk("dep-a")
        assert result["dependency_name"] == "dep-a"
        assert result["risk_score"] == 85.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_dependency_risk("ghost")
        assert result["status"] == "no_data"


class TestIdentifyCriticalRisks:
    def test_with_critical(self):
        eng = _engine()
        eng.record_risk("dep-a", risk_score=95.0)
        eng.record_risk("dep-b", risk_score=20.0)
        results = eng.identify_critical_risks()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_risks() == []


class TestRankByRiskScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_risk("dep-a", risk_score=30.0)
        eng.record_risk("dep-b", risk_score=90.0)
        results = eng.rank_by_risk_score()
        assert results[0]["risk_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


class TestDetectUnmitigatedRisks:
    def test_with_unmitigated(self):
        eng = _engine(critical_threshold=80.0)
        eng.record_risk("dep-a", risk_score=90.0)
        eng.record_risk(
            "dep-b",
            risk_score=90.0,
            mitigation_status=MitigationStatus.FULLY_MITIGATED,
        )
        results = eng.detect_unmitigated_risks()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.detect_unmitigated_risks() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(critical_threshold=80.0)
        eng.record_risk("dep-a", risk_score=95.0)
        eng.record_risk("dep-b", risk_score=20.0)
        eng.record_mitigation("dep-a", "mit-1")
        report = eng.generate_report()
        assert report.total_risks == 2
        assert report.total_mitigations == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_risks == 0
        assert "acceptable" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_risk("dep-a")
        eng.record_mitigation("dep-a", "mit-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._mitigations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_risks"] == 0
        assert stats["total_mitigations"] == 0
        assert stats["risk_factor_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_risk("dep-a", risk_factor=RiskFactor.NO_FALLBACK)
        eng.record_risk("dep-b", risk_factor=RiskFactor.VERSION_LAG)
        eng.record_mitigation("dep-a", "mit-1")
        stats = eng.get_stats()
        assert stats["total_risks"] == 2
        assert stats["total_mitigations"] == 1
        assert stats["unique_dependencies"] == 2
