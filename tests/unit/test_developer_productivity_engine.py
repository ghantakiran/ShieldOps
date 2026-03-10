"""Tests for developer_productivity_engine — DeveloperProductivityEngine."""

from __future__ import annotations

from shieldops.analytics.developer_productivity_engine import (
    DeveloperProductivityEngine,
    ProductivityLevel,
    ProductivityMetric,
    ProductivitySource,
)


def _engine(**kw) -> DeveloperProductivityEngine:
    return DeveloperProductivityEngine(**kw)


class TestEnums:
    def test_productivitymetric_cycle_time(self):
        assert ProductivityMetric.CYCLE_TIME == "cycle_time"

    def test_productivitymetric_code_review_time(self):
        assert ProductivityMetric.CODE_REVIEW_TIME == "code_review_time"

    def test_productivitymetric_deploy_frequency(self):
        assert ProductivityMetric.DEPLOY_FREQUENCY == "deploy_frequency"

    def test_productivitymetric_context_switches(self):
        assert ProductivityMetric.CONTEXT_SWITCHES == "context_switches"

    def test_productivitymetric_flow_state_hours(self):
        assert ProductivityMetric.FLOW_STATE_HOURS == "flow_state_hours"

    def test_productivitylevel_elite(self):
        assert ProductivityLevel.ELITE == "elite"

    def test_productivitylevel_high(self):
        assert ProductivityLevel.HIGH == "high"

    def test_productivitylevel_medium(self):
        assert ProductivityLevel.MEDIUM == "medium"

    def test_productivitylevel_low(self):
        assert ProductivityLevel.LOW == "low"

    def test_productivitylevel_unknown(self):
        assert ProductivityLevel.UNKNOWN == "unknown"

    def test_productivitysource_git(self):
        assert ProductivitySource.GIT == "git"

    def test_productivitysource_ci_cd(self):
        assert ProductivitySource.CI_CD == "ci_cd"

    def test_productivitysource_jira(self):
        assert ProductivitySource.JIRA == "jira"

    def test_productivitysource_ide_telemetry(self):
        assert ProductivitySource.IDE_TELEMETRY == "ide_telemetry"

    def test_productivitysource_survey(self):
        assert ProductivitySource.SURVEY == "survey"


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            name="test-001",
            productivity_metric=ProductivityMetric.CYCLE_TIME,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.productivity_metric == ProductivityMetric.CYCLE_TIME
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.add_record(name="a")
        eng.add_record(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_productivity_metric(self):
        eng = _engine()
        eng.add_record(
            name="a",
            productivity_metric=ProductivityMetric.CYCLE_TIME,
        )
        eng.add_record(
            name="b",
            productivity_metric=ProductivityMetric.CODE_REVIEW_TIME,
        )
        result = eng.list_records(
            productivity_metric=ProductivityMetric.CYCLE_TIME,
        )
        assert len(result) == 1

    def test_filter_by_productivity_level(self):
        eng = _engine()
        eng.add_record(
            name="a",
            productivity_level=ProductivityLevel.ELITE,
        )
        eng.add_record(
            name="b",
            productivity_level=ProductivityLevel.HIGH,
        )
        result = eng.list_records(
            productivity_level=ProductivityLevel.ELITE,
        )
        assert len(result) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.add_record(name="a", team="sec")
        eng.add_record(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.add_record(name=f"a-{i}")
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
        eng.add_record(
            name="a",
            productivity_metric=ProductivityMetric.CYCLE_TIME,
            score=90.0,
        )
        eng.add_record(
            name="b",
            productivity_metric=ProductivityMetric.CYCLE_TIME,
            score=70.0,
        )
        result = eng.analyze_distribution()
        assert "cycle_time" in result
        assert result["cycle_time"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=60.0)
        eng.add_record(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.add_record(name="a", score=50.0)
        eng.add_record(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.add_record(
            name="a",
            service="auth",
            score=90.0,
        )
        eng.add_record(
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
        eng.add_record(name="test", score=50.0)
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
        eng.add_record(name="test")
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
        eng.add_record(
            name="test",
            service="auth",
            team="sec",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
