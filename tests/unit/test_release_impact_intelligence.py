"""Tests for shieldops.changes.release_impact_intelligence — ReleaseImpactIntelligence."""

from __future__ import annotations

from shieldops.changes.release_impact_intelligence import (
    AnalysisPhase,
    ImpactArea,
    ImpactSeverity,
    ReleaseImpactAnalysis,
    ReleaseImpactIntelligence,
    ReleaseImpactRecord,
    ReleaseImpactReport,
)


def _engine(**kw) -> ReleaseImpactIntelligence:
    return ReleaseImpactIntelligence(**kw)


class TestEnums:
    def test_impact_area_performance(self):
        assert ImpactArea.PERFORMANCE == "performance"

    def test_impact_area_reliability(self):
        assert ImpactArea.RELIABILITY == "reliability"

    def test_impact_area_security(self):
        assert ImpactArea.SECURITY == "security"

    def test_impact_area_user_experience(self):
        assert ImpactArea.USER_EXPERIENCE == "user_experience"

    def test_impact_area_cost(self):
        assert ImpactArea.COST == "cost"

    def test_analysis_phase_pre_release(self):
        assert AnalysisPhase.PRE_RELEASE == "pre_release"

    def test_analysis_phase_canary(self):
        assert AnalysisPhase.CANARY == "canary"

    def test_analysis_phase_rollout(self):
        assert AnalysisPhase.ROLLOUT == "rollout"

    def test_analysis_phase_post_release(self):
        assert AnalysisPhase.POST_RELEASE == "post_release"

    def test_analysis_phase_retrospective(self):
        assert AnalysisPhase.RETROSPECTIVE == "retrospective"

    def test_impact_severity_critical(self):
        assert ImpactSeverity.CRITICAL == "critical"

    def test_impact_severity_significant(self):
        assert ImpactSeverity.SIGNIFICANT == "significant"

    def test_impact_severity_moderate(self):
        assert ImpactSeverity.MODERATE == "moderate"

    def test_impact_severity_minor(self):
        assert ImpactSeverity.MINOR == "minor"

    def test_impact_severity_positive(self):
        assert ImpactSeverity.POSITIVE == "positive"


class TestModels:
    def test_record_defaults(self):
        r = ReleaseImpactRecord()
        assert r.id
        assert r.name == ""
        assert r.impact_area == ImpactArea.PERFORMANCE
        assert r.analysis_phase == AnalysisPhase.PRE_RELEASE
        assert r.impact_severity == ImpactSeverity.POSITIVE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ReleaseImpactAnalysis()
        assert a.id
        assert a.name == ""
        assert a.impact_area == ImpactArea.PERFORMANCE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ReleaseImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_impact_area == {}
        assert r.by_analysis_phase == {}
        assert r.by_impact_severity == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            impact_area=ImpactArea.PERFORMANCE,
            analysis_phase=AnalysisPhase.CANARY,
            impact_severity=ImpactSeverity.CRITICAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.impact_area == ImpactArea.PERFORMANCE
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_impact_area(self):
        eng = _engine()
        eng.record_entry(name="a", impact_area=ImpactArea.PERFORMANCE)
        eng.record_entry(name="b", impact_area=ImpactArea.RELIABILITY)
        assert len(eng.list_records(impact_area=ImpactArea.PERFORMANCE)) == 1

    def test_filter_by_analysis_phase(self):
        eng = _engine()
        eng.record_entry(name="a", analysis_phase=AnalysisPhase.PRE_RELEASE)
        eng.record_entry(name="b", analysis_phase=AnalysisPhase.CANARY)
        assert len(eng.list_records(analysis_phase=AnalysisPhase.PRE_RELEASE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
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
        eng.record_entry(name="a", impact_area=ImpactArea.RELIABILITY, score=90.0)
        eng.record_entry(name="b", impact_area=ImpactArea.RELIABILITY, score=70.0)
        result = eng.analyze_distribution()
        assert "reliability" in result
        assert result["reliability"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
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
        eng.record_entry(name="test", score=50.0)
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
        eng.record_entry(name="test")
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
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
