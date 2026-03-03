"""Tests for shieldops.incidents.unified_incident_intelligence — UnifiedIncidentIntelligence."""

from __future__ import annotations

from shieldops.incidents.unified_incident_intelligence import (
    IncidentDomain,
    IncidentPhase,
    IntelligenceType,
    UnifiedIncidentIntelligence,
    UnifiedIncidentIntelligenceAnalysis,
    UnifiedIncidentIntelligenceRecord,
    UnifiedIncidentIntelligenceReport,
)


def _engine(**kw) -> UnifiedIncidentIntelligence:
    return UnifiedIncidentIntelligence(**kw)


class TestEnums:
    def test_incident_domain_first(self):
        assert IncidentDomain.SECURITY == "security"

    def test_incident_domain_second(self):
        assert IncidentDomain.AVAILABILITY == "availability"

    def test_incident_domain_third(self):
        assert IncidentDomain.PERFORMANCE == "performance"

    def test_incident_domain_fourth(self):
        assert IncidentDomain.COMPLIANCE == "compliance"

    def test_incident_domain_fifth(self):
        assert IncidentDomain.DATA == "data"

    def test_intelligence_type_first(self):
        assert IntelligenceType.ROOT_CAUSE == "root_cause"

    def test_intelligence_type_second(self):
        assert IntelligenceType.IMPACT == "impact"

    def test_intelligence_type_third(self):
        assert IntelligenceType.CORRELATION == "correlation"

    def test_intelligence_type_fourth(self):
        assert IntelligenceType.PREDICTION == "prediction"

    def test_intelligence_type_fifth(self):
        assert IntelligenceType.RECOMMENDATION == "recommendation"

    def test_incident_phase_first(self):
        assert IncidentPhase.DETECTION == "detection"

    def test_incident_phase_second(self):
        assert IncidentPhase.TRIAGE == "triage"

    def test_incident_phase_third(self):
        assert IncidentPhase.CONTAINMENT == "containment"

    def test_incident_phase_fourth(self):
        assert IncidentPhase.ERADICATION == "eradication"

    def test_incident_phase_fifth(self):
        assert IncidentPhase.RECOVERY == "recovery"


class TestModels:
    def test_record_defaults(self):
        r = UnifiedIncidentIntelligenceRecord()
        assert r.id
        assert r.name == ""
        assert r.incident_domain == IncidentDomain.SECURITY
        assert r.intelligence_type == IntelligenceType.ROOT_CAUSE
        assert r.incident_phase == IncidentPhase.DETECTION
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = UnifiedIncidentIntelligenceAnalysis()
        assert a.id
        assert a.name == ""
        assert a.incident_domain == IncidentDomain.SECURITY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = UnifiedIncidentIntelligenceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_incident_domain == {}
        assert r.by_intelligence_type == {}
        assert r.by_incident_phase == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            incident_domain=IncidentDomain.SECURITY,
            intelligence_type=IntelligenceType.IMPACT,
            incident_phase=IncidentPhase.CONTAINMENT,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.incident_domain == IncidentDomain.SECURITY
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_incident_domain(self):
        eng = _engine()
        eng.record_item(name="a", incident_domain=IncidentDomain.AVAILABILITY)
        eng.record_item(name="b", incident_domain=IncidentDomain.SECURITY)
        assert len(eng.list_records(incident_domain=IncidentDomain.AVAILABILITY)) == 1

    def test_filter_by_intelligence_type(self):
        eng = _engine()
        eng.record_item(name="a", intelligence_type=IntelligenceType.ROOT_CAUSE)
        eng.record_item(name="b", intelligence_type=IntelligenceType.IMPACT)
        assert len(eng.list_records(intelligence_type=IntelligenceType.ROOT_CAUSE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(name="a", incident_domain=IncidentDomain.AVAILABILITY, score=90.0)
        eng.record_item(name="b", incident_domain=IncidentDomain.AVAILABILITY, score=70.0)
        result = eng.analyze_distribution()
        assert "availability" in result
        assert result["availability"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(name="a", service="auth", score=90.0)
        eng.record_item(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_item(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
