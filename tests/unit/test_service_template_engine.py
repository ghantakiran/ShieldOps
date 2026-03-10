"""Tests for service_template_engine — ServiceTemplateEngine."""

from __future__ import annotations

from shieldops.changes.service_template_engine import (
    ScaffoldOutcome,
    ServiceTemplateEngine,
    TemplateMaturity,
    TemplateType,
)


def _engine(**kw) -> ServiceTemplateEngine:
    return ServiceTemplateEngine(**kw)


class TestEnums:
    def test_templatetype_microservice(self):
        assert TemplateType.MICROSERVICE == "microservice"

    def test_templatetype_library(self):
        assert TemplateType.LIBRARY == "library"

    def test_templatetype_frontend(self):
        assert TemplateType.FRONTEND == "frontend"

    def test_templatetype_data_pipeline(self):
        assert TemplateType.DATA_PIPELINE == "data_pipeline"

    def test_templatetype_infrastructure(self):
        assert TemplateType.INFRASTRUCTURE == "infrastructure"

    def test_templatematurity_experimental(self):
        assert TemplateMaturity.EXPERIMENTAL == "experimental"

    def test_templatematurity_beta(self):
        assert TemplateMaturity.BETA == "beta"

    def test_templatematurity_stable(self):
        assert TemplateMaturity.STABLE == "stable"

    def test_templatematurity_deprecated(self):
        assert TemplateMaturity.DEPRECATED == "deprecated"

    def test_templatematurity_archived(self):
        assert TemplateMaturity.ARCHIVED == "archived"

    def test_scaffoldoutcome_success(self):
        assert ScaffoldOutcome.SUCCESS == "success"

    def test_scaffoldoutcome_partial(self):
        assert ScaffoldOutcome.PARTIAL == "partial"

    def test_scaffoldoutcome_failed(self):
        assert ScaffoldOutcome.FAILED == "failed"

    def test_scaffoldoutcome_skipped(self):
        assert ScaffoldOutcome.SKIPPED == "skipped"

    def test_scaffoldoutcome_custom_override(self):
        assert ScaffoldOutcome.CUSTOM_OVERRIDE == "custom_override"


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            template_type=TemplateType.MICROSERVICE,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.template_type == TemplateType.MICROSERVICE
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

    def test_filter_by_template_type(self):
        eng = _engine()
        eng.record_item(
            name="a",
            template_type=TemplateType.MICROSERVICE,
        )
        eng.record_item(
            name="b",
            template_type=TemplateType.LIBRARY,
        )
        result = eng.list_records(
            template_type=TemplateType.MICROSERVICE,
        )
        assert len(result) == 1

    def test_filter_by_template_maturity(self):
        eng = _engine()
        eng.record_item(
            name="a",
            template_maturity=TemplateMaturity.STABLE,
        )
        eng.record_item(
            name="b",
            template_maturity=TemplateMaturity.BETA,
        )
        result = eng.list_records(
            template_maturity=TemplateMaturity.STABLE,
        )
        assert len(result) == 1

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
        eng.record_item(
            name="a",
            template_type=TemplateType.MICROSERVICE,
            score=90.0,
        )
        eng.record_item(
            name="b",
            template_type=TemplateType.MICROSERVICE,
            score=70.0,
        )
        result = eng.analyze_distribution()
        assert "microservice" in result
        assert result["microservice"]["count"] == 2

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
        eng.record_item(
            name="a",
            service="auth",
            score=90.0,
        )
        eng.record_item(
            name="b",
            service="api",
            score=50.0,
        )
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(
                name="t",
                analysis_score=50.0,
            )
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(
            name="a",
            analysis_score=20.0,
        )
        eng.add_analysis(
            name="b",
            analysis_score=20.0,
        )
        eng.add_analysis(
            name="c",
            analysis_score=80.0,
        )
        eng.add_analysis(
            name="d",
            analysis_score=80.0,
        )
        result = eng.detect_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


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
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_item(
            name="test",
            service="auth",
            team="sec",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
