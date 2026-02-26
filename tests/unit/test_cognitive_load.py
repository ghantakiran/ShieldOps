"""Tests for shieldops.operations.cognitive_load — TeamCognitiveLoadTracker."""

from __future__ import annotations

from shieldops.operations.cognitive_load import (
    CognitiveLoadRecord,
    CognitiveLoadReport,
    LoadContributor,
    LoadLevel,
    LoadSource,
    LoadTrend,
    TeamCognitiveLoadTracker,
)


def _engine(**kw) -> TeamCognitiveLoadTracker:
    return TeamCognitiveLoadTracker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # LoadSource (5)
    def test_source_alert_volume(self):
        assert LoadSource.ALERT_VOLUME == "alert_volume"

    def test_source_context_switching(self):
        assert LoadSource.CONTEXT_SWITCHING == "context_switching"

    def test_source_concurrent_incidents(self):
        assert LoadSource.CONCURRENT_INCIDENTS == "concurrent_incidents"

    def test_source_deployment_frequency(self):
        assert LoadSource.DEPLOYMENT_FREQUENCY == "deployment_frequency"

    def test_source_toil(self):
        assert LoadSource.TOIL == "toil"

    # LoadLevel (5)
    def test_level_critical(self):
        assert LoadLevel.CRITICAL == "critical"

    def test_level_high(self):
        assert LoadLevel.HIGH == "high"

    def test_level_moderate(self):
        assert LoadLevel.MODERATE == "moderate"

    def test_level_low(self):
        assert LoadLevel.LOW == "low"

    def test_level_minimal(self):
        assert LoadLevel.MINIMAL == "minimal"

    # LoadTrend (5)
    def test_trend_worsening(self):
        assert LoadTrend.WORSENING == "worsening"

    def test_trend_stable(self):
        assert LoadTrend.STABLE == "stable"

    def test_trend_improving(self):
        assert LoadTrend.IMPROVING == "improving"

    def test_trend_volatile(self):
        assert LoadTrend.VOLATILE == "volatile"

    def test_trend_insufficient_data(self):
        assert LoadTrend.INSUFFICIENT_DATA == "insufficient_data"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_cognitive_load_record_defaults(self):
        r = CognitiveLoadRecord()
        assert r.id
        assert r.team_name == ""
        assert r.source == LoadSource.ALERT_VOLUME
        assert r.level == LoadLevel.MODERATE
        assert r.load_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_load_contributor_defaults(self):
        r = LoadContributor()
        assert r.id
        assert r.contributor_name == ""
        assert r.source == LoadSource.ALERT_VOLUME
        assert r.level == LoadLevel.MODERATE
        assert r.impact_score == 0.0
        assert r.description == ""
        assert r.created_at > 0

    def test_cognitive_load_report_defaults(self):
        r = CognitiveLoadReport()
        assert r.total_loads == 0
        assert r.total_contributors == 0
        assert r.avg_load_score_pct == 0.0
        assert r.by_source == {}
        assert r.by_level == {}
        assert r.overloaded_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_load
# -------------------------------------------------------------------


class TestRecordLoad:
    def test_basic(self):
        eng = _engine()
        r = eng.record_load(
            "team-alpha",
            source=LoadSource.ALERT_VOLUME,
            level=LoadLevel.HIGH,
        )
        assert r.team_name == "team-alpha"
        assert r.source == LoadSource.ALERT_VOLUME

    def test_with_score(self):
        eng = _engine()
        r = eng.record_load("team-beta", load_score=85.0)
        assert r.load_score == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_load(f"team-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_load
# -------------------------------------------------------------------


class TestGetLoad:
    def test_found(self):
        eng = _engine()
        r = eng.record_load("team-alpha")
        assert eng.get_load(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_load("nonexistent") is None


# -------------------------------------------------------------------
# list_loads
# -------------------------------------------------------------------


class TestListLoads:
    def test_list_all(self):
        eng = _engine()
        eng.record_load("team-alpha")
        eng.record_load("team-beta")
        assert len(eng.list_loads()) == 2

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_load("team-alpha")
        eng.record_load("team-beta")
        results = eng.list_loads(team_name="team-alpha")
        assert len(results) == 1

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_load("team-alpha", source=LoadSource.CONTEXT_SWITCHING)
        eng.record_load("team-beta", source=LoadSource.ALERT_VOLUME)
        results = eng.list_loads(source=LoadSource.CONTEXT_SWITCHING)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_contributor
# -------------------------------------------------------------------


class TestAddContributor:
    def test_basic(self):
        eng = _engine()
        c = eng.add_contributor(
            "noisy-alerts",
            source=LoadSource.ALERT_VOLUME,
            level=LoadLevel.HIGH,
            impact_score=75.0,
            description="High alert noise",
        )
        assert c.contributor_name == "noisy-alerts"
        assert c.impact_score == 75.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_contributor(f"contrib-{i}")
        assert len(eng._contributors) == 2


# -------------------------------------------------------------------
# analyze_team_load
# -------------------------------------------------------------------


class TestAnalyzeTeamLoad:
    def test_with_data(self):
        eng = _engine()
        eng.record_load("team-alpha", load_score=90.0, level=LoadLevel.CRITICAL)
        eng.record_load("team-alpha", load_score=70.0, level=LoadLevel.LOW)
        result = eng.analyze_team_load("team-alpha")
        assert result["team_name"] == "team-alpha"
        assert result["total_records"] == 2
        assert result["avg_load_score"] == 80.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_team_load("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_overloaded_teams
# -------------------------------------------------------------------


class TestIdentifyOverloadedTeams:
    def test_with_overloaded(self):
        eng = _engine()
        eng.record_load("team-alpha", level=LoadLevel.CRITICAL)
        eng.record_load("team-alpha", level=LoadLevel.HIGH)
        eng.record_load("team-beta", level=LoadLevel.LOW)
        results = eng.identify_overloaded_teams()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-alpha"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overloaded_teams() == []


# -------------------------------------------------------------------
# rank_by_load_score
# -------------------------------------------------------------------


class TestRankByLoadScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_load("team-alpha", load_score=90.0)
        eng.record_load("team-alpha", load_score=80.0)
        eng.record_load("team-beta", load_score=30.0)
        results = eng.rank_by_load_score()
        assert results[0]["team_name"] == "team-alpha"
        assert results[0]["avg_load_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_load_score() == []


# -------------------------------------------------------------------
# detect_load_trends
# -------------------------------------------------------------------


class TestDetectLoadTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_load("team-alpha")
        eng.record_load("team-beta")
        results = eng.detect_load_trends()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-alpha"
        assert results[0]["trend_detected"] is True

    def test_no_trends(self):
        eng = _engine()
        eng.record_load("team-alpha")
        assert eng.detect_load_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_load("team-alpha", level=LoadLevel.CRITICAL, load_score=90.0)
        eng.record_load("team-beta", level=LoadLevel.LOW, load_score=20.0)
        eng.add_contributor("contrib-1")
        report = eng.generate_report()
        assert report.total_loads == 2
        assert report.total_contributors == 1
        assert report.by_source != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_loads == 0
        assert "within acceptable" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_load("team-alpha")
        eng.add_contributor("contrib-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._contributors) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_loads"] == 0
        assert stats["total_contributors"] == 0
        assert stats["source_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_load("team-alpha", source=LoadSource.ALERT_VOLUME)
        eng.record_load("team-beta", source=LoadSource.CONTEXT_SWITCHING)
        eng.add_contributor("contrib-1")
        stats = eng.get_stats()
        assert stats["total_loads"] == 2
        assert stats["total_contributors"] == 1
        assert stats["unique_teams"] == 2
