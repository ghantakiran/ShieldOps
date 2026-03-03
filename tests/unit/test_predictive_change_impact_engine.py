"""Tests for shieldops.changes.predictive_change_impact_engine — PredictiveChangeImpactEngine."""

from __future__ import annotations

from shieldops.changes.predictive_change_impact_engine import (
    ChangeType,
    ImpactLikelihood,
    ImpactScope,
    PredictiveChangeImpactEngine,
    PredictiveChangeImpactEngineAnalysis,
    PredictiveChangeImpactEngineRecord,
    PredictiveChangeImpactEngineReport,
)


def _engine(**kw) -> PredictiveChangeImpactEngine:
    return PredictiveChangeImpactEngine(**kw)


class TestEnums:
    def test_change_type_first(self):
        assert ChangeType.CODE_DEPLOY == "code_deploy"

    def test_change_type_second(self):
        assert ChangeType.CONFIG_CHANGE == "config_change"

    def test_change_type_third(self):
        assert ChangeType.INFRA_CHANGE == "infra_change"

    def test_change_type_fourth(self):
        assert ChangeType.DEPENDENCY_UPDATE == "dependency_update"

    def test_change_type_fifth(self):
        assert ChangeType.POLICY_CHANGE == "policy_change"

    def test_impact_scope_first(self):
        assert ImpactScope.SERVICE == "service"

    def test_impact_scope_second(self):
        assert ImpactScope.TEAM == "team"

    def test_impact_scope_third(self):
        assert ImpactScope.DEPARTMENT == "department"

    def test_impact_scope_fourth(self):
        assert ImpactScope.ORGANIZATION == "organization"

    def test_impact_scope_fifth(self):
        assert ImpactScope.EXTERNAL == "external"

    def test_impact_likelihood_first(self):
        assert ImpactLikelihood.CERTAIN == "certain"

    def test_impact_likelihood_second(self):
        assert ImpactLikelihood.LIKELY == "likely"

    def test_impact_likelihood_third(self):
        assert ImpactLikelihood.POSSIBLE == "possible"

    def test_impact_likelihood_fourth(self):
        assert ImpactLikelihood.UNLIKELY == "unlikely"

    def test_impact_likelihood_fifth(self):
        assert ImpactLikelihood.RARE == "rare"


class TestModels:
    def test_record_defaults(self):
        r = PredictiveChangeImpactEngineRecord()
        assert r.id
        assert r.name == ""
        assert r.change_type == ChangeType.CODE_DEPLOY
        assert r.impact_scope == ImpactScope.SERVICE
        assert r.impact_likelihood == ImpactLikelihood.CERTAIN
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = PredictiveChangeImpactEngineAnalysis()
        assert a.id
        assert a.name == ""
        assert a.change_type == ChangeType.CODE_DEPLOY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = PredictiveChangeImpactEngineReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_change_type == {}
        assert r.by_impact_scope == {}
        assert r.by_impact_likelihood == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            change_type=ChangeType.CODE_DEPLOY,
            impact_scope=ImpactScope.TEAM,
            impact_likelihood=ImpactLikelihood.POSSIBLE,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.change_type == ChangeType.CODE_DEPLOY
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

    def test_filter_by_change_type(self):
        eng = _engine()
        eng.record_item(name="a", change_type=ChangeType.CONFIG_CHANGE)
        eng.record_item(name="b", change_type=ChangeType.CODE_DEPLOY)
        assert len(eng.list_records(change_type=ChangeType.CONFIG_CHANGE)) == 1

    def test_filter_by_impact_scope(self):
        eng = _engine()
        eng.record_item(name="a", impact_scope=ImpactScope.SERVICE)
        eng.record_item(name="b", impact_scope=ImpactScope.TEAM)
        assert len(eng.list_records(impact_scope=ImpactScope.SERVICE)) == 1

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
        eng.record_item(name="a", change_type=ChangeType.CONFIG_CHANGE, score=90.0)
        eng.record_item(name="b", change_type=ChangeType.CONFIG_CHANGE, score=70.0)
        result = eng.analyze_distribution()
        assert "config_change" in result
        assert result["config_change"]["count"] == 2

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
