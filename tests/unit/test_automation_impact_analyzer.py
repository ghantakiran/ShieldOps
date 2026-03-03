"""Tests for shieldops.analytics.automation_impact_analyzer — AutomationImpactAnalyzer."""

from __future__ import annotations

from shieldops.analytics.automation_impact_analyzer import (
    AutomationImpactAnalyzer,
    AutomationImpactReport,
    AutomationType,
    ImpactAnalysis,
    ImpactLevel,
    ImpactMetric,
    ImpactRecord,
)


def _engine(**kw) -> AutomationImpactAnalyzer:
    return AutomationImpactAnalyzer(**kw)


class TestEnums:
    def test_automation_type_runbook(self):
        assert AutomationType.RUNBOOK == "runbook"

    def test_automation_type_scaling(self):
        assert AutomationType.SCALING == "scaling"

    def test_automation_type_remediation(self):
        assert AutomationType.REMEDIATION == "remediation"

    def test_automation_type_deployment(self):
        assert AutomationType.DEPLOYMENT == "deployment"

    def test_automation_type_security(self):
        assert AutomationType.SECURITY == "security"

    def test_impact_metric_time_saved(self):
        assert ImpactMetric.TIME_SAVED == "time_saved"

    def test_impact_metric_incidents_prevented(self):
        assert ImpactMetric.INCIDENTS_PREVENTED == "incidents_prevented"

    def test_impact_metric_cost_reduction(self):
        assert ImpactMetric.COST_REDUCTION == "cost_reduction"

    def test_impact_metric_mttr_improvement(self):
        assert ImpactMetric.MTTR_IMPROVEMENT == "mttr_improvement"

    def test_impact_metric_toil_reduction(self):
        assert ImpactMetric.TOIL_REDUCTION == "toil_reduction"

    def test_impact_level_transformative(self):
        assert ImpactLevel.TRANSFORMATIVE == "transformative"

    def test_impact_level_significant(self):
        assert ImpactLevel.SIGNIFICANT == "significant"

    def test_impact_level_moderate(self):
        assert ImpactLevel.MODERATE == "moderate"

    def test_impact_level_marginal(self):
        assert ImpactLevel.MARGINAL == "marginal"

    def test_impact_level_negligible(self):
        assert ImpactLevel.NEGLIGIBLE == "negligible"


class TestModels:
    def test_record_defaults(self):
        r = ImpactRecord()
        assert r.id
        assert r.name == ""
        assert r.automation_type == AutomationType.RUNBOOK
        assert r.impact_metric == ImpactMetric.TIME_SAVED
        assert r.impact_level == ImpactLevel.NEGLIGIBLE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ImpactAnalysis()
        assert a.id
        assert a.name == ""
        assert a.automation_type == AutomationType.RUNBOOK
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AutomationImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_automation_type == {}
        assert r.by_impact_metric == {}
        assert r.by_impact_level == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            automation_type=AutomationType.RUNBOOK,
            impact_metric=ImpactMetric.INCIDENTS_PREVENTED,
            impact_level=ImpactLevel.TRANSFORMATIVE,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.automation_type == AutomationType.RUNBOOK
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

    def test_filter_by_automation_type(self):
        eng = _engine()
        eng.record_entry(name="a", automation_type=AutomationType.RUNBOOK)
        eng.record_entry(name="b", automation_type=AutomationType.SCALING)
        assert len(eng.list_records(automation_type=AutomationType.RUNBOOK)) == 1

    def test_filter_by_impact_metric(self):
        eng = _engine()
        eng.record_entry(name="a", impact_metric=ImpactMetric.TIME_SAVED)
        eng.record_entry(name="b", impact_metric=ImpactMetric.INCIDENTS_PREVENTED)
        assert len(eng.list_records(impact_metric=ImpactMetric.TIME_SAVED)) == 1

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
        eng.record_entry(name="a", automation_type=AutomationType.SCALING, score=90.0)
        eng.record_entry(name="b", automation_type=AutomationType.SCALING, score=70.0)
        result = eng.analyze_distribution()
        assert "scaling" in result
        assert result["scaling"]["count"] == 2

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
