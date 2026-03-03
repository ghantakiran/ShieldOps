"""Tests for shieldops.analytics.autonomous_ops_maturity_scorer — AutonomousOpsMaturityScorer."""

from __future__ import annotations

from shieldops.analytics.autonomous_ops_maturity_scorer import (
    AssessmentSource,
    AutonomousOpsMaturityReport,
    AutonomousOpsMaturityScorer,
    MaturityPillar,
    MaturityPillarAnalysis,
    MaturityPillarRecord,
    MaturityTier,
)


def _engine(**kw) -> AutonomousOpsMaturityScorer:
    return AutonomousOpsMaturityScorer(**kw)


class TestEnums:
    def test_maturity_pillar_automation(self):
        assert MaturityPillar.AUTOMATION == "automation"

    def test_maturity_pillar_observability(self):
        assert MaturityPillar.OBSERVABILITY == "observability"

    def test_maturity_pillar_incident_management(self):
        assert MaturityPillar.INCIDENT_MANAGEMENT == "incident_management"

    def test_maturity_pillar_capacity(self):
        assert MaturityPillar.CAPACITY == "capacity"

    def test_maturity_pillar_security(self):
        assert MaturityPillar.SECURITY == "security"

    def test_assessment_source_automated_scan(self):
        assert AssessmentSource.AUTOMATED_SCAN == "automated_scan"

    def test_assessment_source_manual_review(self):
        assert AssessmentSource.MANUAL_REVIEW == "manual_review"

    def test_assessment_source_benchmark(self):
        assert AssessmentSource.BENCHMARK == "benchmark"

    def test_assessment_source_survey(self):
        assert AssessmentSource.SURVEY == "survey"

    def test_assessment_source_integration_check(self):
        assert AssessmentSource.INTEGRATION_CHECK == "integration_check"

    def test_maturity_tier_autonomous(self):
        assert MaturityTier.AUTONOMOUS == "autonomous"

    def test_maturity_tier_proactive(self):
        assert MaturityTier.PROACTIVE == "proactive"

    def test_maturity_tier_reactive(self):
        assert MaturityTier.REACTIVE == "reactive"

    def test_maturity_tier_manual(self):
        assert MaturityTier.MANUAL == "manual"

    def test_maturity_tier_ad_hoc(self):
        assert MaturityTier.AD_HOC == "ad_hoc"


class TestModels:
    def test_record_defaults(self):
        r = MaturityPillarRecord()
        assert r.id
        assert r.name == ""
        assert r.maturity_pillar == MaturityPillar.AUTOMATION
        assert r.assessment_source == AssessmentSource.AUTOMATED_SCAN
        assert r.maturity_tier == MaturityTier.AD_HOC
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = MaturityPillarAnalysis()
        assert a.id
        assert a.name == ""
        assert a.maturity_pillar == MaturityPillar.AUTOMATION
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AutonomousOpsMaturityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_maturity_pillar == {}
        assert r.by_assessment_source == {}
        assert r.by_maturity_tier == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            maturity_pillar=MaturityPillar.AUTOMATION,
            assessment_source=AssessmentSource.MANUAL_REVIEW,
            maturity_tier=MaturityTier.AUTONOMOUS,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.maturity_pillar == MaturityPillar.AUTOMATION
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

    def test_filter_by_maturity_pillar(self):
        eng = _engine()
        eng.record_entry(name="a", maturity_pillar=MaturityPillar.AUTOMATION)
        eng.record_entry(name="b", maturity_pillar=MaturityPillar.OBSERVABILITY)
        assert len(eng.list_records(maturity_pillar=MaturityPillar.AUTOMATION)) == 1

    def test_filter_by_assessment_source(self):
        eng = _engine()
        eng.record_entry(name="a", assessment_source=AssessmentSource.AUTOMATED_SCAN)
        eng.record_entry(name="b", assessment_source=AssessmentSource.MANUAL_REVIEW)
        assert len(eng.list_records(assessment_source=AssessmentSource.AUTOMATED_SCAN)) == 1

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
        eng.record_entry(name="a", maturity_pillar=MaturityPillar.OBSERVABILITY, score=90.0)
        eng.record_entry(name="b", maturity_pillar=MaturityPillar.OBSERVABILITY, score=70.0)
        result = eng.analyze_distribution()
        assert "observability" in result
        assert result["observability"]["count"] == 2

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
