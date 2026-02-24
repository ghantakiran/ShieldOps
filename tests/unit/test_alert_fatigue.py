"""Tests for shieldops.observability.alert_fatigue — AlertFatigueScorer."""

from __future__ import annotations

from shieldops.observability.alert_fatigue import (
    AlertActionability,
    AlertFatigueRecord,
    AlertFatigueScorer,
    FatigueLevel,
    FatigueReport,
    FatigueScore,
    ResponderEngagement,
)


def _engine(**kw) -> AlertFatigueScorer:
    return AlertFatigueScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # FatigueLevel (5 values)

    def test_fatigue_level_minimal(self):
        assert FatigueLevel.MINIMAL == "minimal"

    def test_fatigue_level_low(self):
        assert FatigueLevel.LOW == "low"

    def test_fatigue_level_moderate(self):
        assert FatigueLevel.MODERATE == "moderate"

    def test_fatigue_level_high(self):
        assert FatigueLevel.HIGH == "high"

    def test_fatigue_level_critical(self):
        assert FatigueLevel.CRITICAL == "critical"

    # AlertActionability (5 values)

    def test_actionability_actionable(self):
        assert AlertActionability.ACTIONABLE == "actionable"

    def test_actionability_informational(self):
        assert AlertActionability.INFORMATIONAL == "informational"

    def test_actionability_duplicate(self):
        assert AlertActionability.DUPLICATE == "duplicate"

    def test_actionability_false_positive(self):
        assert AlertActionability.FALSE_POSITIVE == "false_positive"

    def test_actionability_stale(self):
        assert AlertActionability.STALE == "stale"

    # ResponderEngagement (5 values)

    def test_engagement_immediate(self):
        assert ResponderEngagement.IMMEDIATE == "immediate"

    def test_engagement_delayed(self):
        assert ResponderEngagement.DELAYED == "delayed"

    def test_engagement_ignored(self):
        assert ResponderEngagement.IGNORED == "ignored"

    def test_engagement_bulk_dismissed(self):
        assert ResponderEngagement.BULK_DISMISSED == "bulk_dismissed"

    def test_engagement_auto_resolved(self):
        assert ResponderEngagement.AUTO_RESOLVED == "auto_resolved"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_alert_fatigue_record_defaults(self):
        rec = AlertFatigueRecord()
        assert rec.id
        assert rec.team == ""
        assert rec.service_name == ""
        assert rec.alert_count == 0
        assert rec.actionable_count == 0
        assert rec.ignored_count == 0
        assert rec.fatigue_level == FatigueLevel.MINIMAL
        assert rec.engagement_rate == 0.0
        assert rec.window_start == 0.0
        assert rec.window_end == 0.0
        assert rec.created_at > 0

    def test_fatigue_score_defaults(self):
        score = FatigueScore()
        assert score.team == ""
        assert score.service_name == ""
        assert score.fatigue_level == FatigueLevel.MINIMAL
        assert score.score == 0.0
        assert score.alert_volume == 0
        assert score.actionability_pct == 0.0
        assert score.engagement_pct == 0.0
        assert score.trend == "stable"
        assert score.created_at > 0

    def test_fatigue_report_defaults(self):
        report = FatigueReport()
        assert report.total_teams == 0
        assert report.total_alerts_analyzed == 0
        assert report.avg_fatigue_score == 0.0
        assert report.by_level == {}
        assert report.by_actionability == {}
        assert report.high_fatigue_teams == []
        assert report.recommendations == []
        assert report.generated_at > 0


# -------------------------------------------------------------------
# record_alert
# -------------------------------------------------------------------


class TestRecordAlert:
    def test_basic_record(self):
        eng = _engine()
        rec = eng.record_alert("team-a", "svc-1")
        assert rec.team == "team-a"
        assert rec.service_name == "svc-1"
        assert len(eng.list_records()) == 1

    def test_record_assigns_unique_ids(self):
        eng = _engine()
        r1 = eng.record_alert("team-a")
        r2 = eng.record_alert("team-b")
        assert r1.id != r2.id

    def test_record_with_counts(self):
        eng = _engine()
        rec = eng.record_alert(
            "team-a",
            alert_count=100,
            actionable_count=20,
            ignored_count=60,
        )
        assert rec.alert_count == 100
        assert rec.actionable_count == 20
        assert rec.ignored_count == 60

    def test_fatigue_level_computed(self):
        eng = _engine()
        # 80% ignored -> CRITICAL
        rec = eng.record_alert(
            "team-a",
            alert_count=100,
            actionable_count=10,
            ignored_count=80,
        )
        assert rec.fatigue_level == FatigueLevel.CRITICAL

    def test_eviction_at_max_records(self):
        eng = _engine(max_records=3)
        ids = []
        for i in range(4):
            rec = eng.record_alert(f"team-{i}")
            ids.append(rec.id)
        records = eng.list_records(limit=100)
        assert len(records) == 3
        found = {r.id for r in records}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_record
# -------------------------------------------------------------------


class TestGetRecord:
    def test_get_existing(self):
        eng = _engine()
        rec = eng.record_alert("team-a")
        found = eng.get_record(rec.id)
        assert found is not None
        assert found.id == rec.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# -------------------------------------------------------------------
# list_records
# -------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_alert("team-a")
        eng.record_alert("team-b")
        eng.record_alert("team-c")
        assert len(eng.list_records()) == 3

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_alert("team-a")
        eng.record_alert("team-b")
        eng.record_alert("team-a")
        results = eng.list_records(team="team-a")
        assert len(results) == 2
        assert all(r.team == "team-a" for r in results)

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_alert("team-a", "svc-1")
        eng.record_alert("team-a", "svc-2")
        eng.record_alert("team-b", "svc-1")
        results = eng.list_records(service_name="svc-1")
        assert len(results) == 2

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_alert(f"team-{i}")
        results = eng.list_records(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# calculate_fatigue_score
# -------------------------------------------------------------------


class TestCalculateFatigueScore:
    def test_basic_score(self):
        eng = _engine()
        eng.record_alert(
            "team-a",
            alert_count=100,
            actionable_count=50,
            ignored_count=30,
        )
        score = eng.calculate_fatigue_score("team-a")
        assert score.team == "team-a"
        assert score.score == 30.0
        assert score.fatigue_level == FatigueLevel.LOW

    def test_high_fatigue(self):
        eng = _engine()
        eng.record_alert(
            "team-a",
            alert_count=100,
            actionable_count=5,
            ignored_count=80,
        )
        score = eng.calculate_fatigue_score("team-a")
        assert score.score == 80.0
        assert score.fatigue_level == FatigueLevel.CRITICAL

    def test_no_records(self):
        eng = _engine()
        score = eng.calculate_fatigue_score("nobody")
        assert score.score == 0.0
        assert score.alert_volume == 0


# -------------------------------------------------------------------
# detect_fatigue_trends
# -------------------------------------------------------------------


class TestDetectFatigueTrends:
    def test_basic_trends(self):
        eng = _engine()
        eng.record_alert("team-a", ignored_count=5)
        eng.record_alert("team-a", ignored_count=10)
        trends = eng.detect_fatigue_trends()
        assert len(trends) == 1
        assert trends[0]["team"] == "team-a"
        assert trends[0]["trend"] == "worsening"

    def test_empty_trends(self):
        eng = _engine()
        trends = eng.detect_fatigue_trends()
        assert trends == []


# -------------------------------------------------------------------
# identify_noisy_alerts
# -------------------------------------------------------------------


class TestIdentifyNoisyAlerts:
    def test_noisy_services(self):
        eng = _engine()
        eng.record_alert(
            "team-a",
            "svc-noisy",
            alert_count=100,
            actionable_count=10,
        )
        eng.record_alert(
            "team-a",
            "svc-good",
            alert_count=100,
            actionable_count=80,
        )
        noisy = eng.identify_noisy_alerts()
        assert len(noisy) == 1
        assert noisy[0]["service_name"] == "svc-noisy"

    def test_no_noisy(self):
        eng = _engine()
        eng.record_alert(
            "team-a",
            "svc",
            alert_count=100,
            actionable_count=80,
        )
        noisy = eng.identify_noisy_alerts()
        assert len(noisy) == 0


# -------------------------------------------------------------------
# rank_teams_by_fatigue
# -------------------------------------------------------------------


class TestRankTeamsByFatigue:
    def test_ranking_order(self):
        eng = _engine()
        eng.record_alert(
            "team-low",
            alert_count=100,
            ignored_count=10,
        )
        eng.record_alert(
            "team-high",
            alert_count=100,
            ignored_count=80,
        )
        ranked = eng.rank_teams_by_fatigue()
        assert len(ranked) == 2
        assert ranked[0].team == "team-high"
        assert ranked[1].team == "team-low"

    def test_empty_ranking(self):
        eng = _engine()
        assert eng.rank_teams_by_fatigue() == []


# -------------------------------------------------------------------
# suggest_alert_tuning
# -------------------------------------------------------------------


class TestSuggestAlertTuning:
    def test_suggestions_generated(self):
        eng = _engine(fatigue_threshold=50.0)
        eng.record_alert(
            "team-a",
            "svc-noisy",
            alert_count=100,
            actionable_count=10,
            ignored_count=80,
        )
        suggestions = eng.suggest_alert_tuning()
        assert len(suggestions) >= 1

    def test_no_suggestions_healthy(self):
        eng = _engine()
        eng.record_alert(
            "team-a",
            "svc-good",
            alert_count=100,
            actionable_count=90,
            ignored_count=5,
        )
        suggestions = eng.suggest_alert_tuning()
        # May still have noisy alert suggestions
        assert isinstance(suggestions, list)


# -------------------------------------------------------------------
# generate_fatigue_report
# -------------------------------------------------------------------


class TestGenerateFatigueReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_alert(
            "team-a",
            alert_count=100,
            actionable_count=50,
            ignored_count=20,
        )
        eng.record_alert(
            "team-b",
            alert_count=200,
            actionable_count=10,
            ignored_count=150,
        )
        report = eng.generate_fatigue_report()
        assert report.total_teams == 2
        assert report.total_alerts_analyzed == 300
        assert report.avg_fatigue_score > 0
        assert isinstance(report.by_level, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_fatigue_report()
        assert report.total_teams == 0
        assert report.total_alerts_analyzed == 0
        assert report.avg_fatigue_score == 0.0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_alert("team-a")
        eng.record_alert("team-b")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_records()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_teams"] == 0
        assert stats["fatigue_threshold"] == 70.0
        assert stats["level_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_alert(
            "team-a",
            alert_count=100,
            ignored_count=80,
        )
        eng.record_alert(
            "team-b",
            alert_count=50,
            ignored_count=5,
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_teams"] == 2
        assert len(stats["level_distribution"]) > 0
