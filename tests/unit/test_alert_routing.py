"""Tests for shieldops.observability.alert_routing — AlertRoutingOptimizer."""

from __future__ import annotations

from shieldops.observability.alert_routing import (
    ActionTaken,
    AlertRoutingOptimizer,
    RoutingAnalysisReport,
    RoutingChannel,
    RoutingEffectiveness,
    RoutingRecommendation,
    RoutingRecord,
)


def _engine(**kw) -> AlertRoutingOptimizer:
    return AlertRoutingOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # RoutingChannel (6)
    def test_channel_slack(self):
        assert RoutingChannel.SLACK == "slack"

    def test_channel_pagerduty(self):
        assert RoutingChannel.PAGERDUTY == "pagerduty"

    def test_channel_email(self):
        assert RoutingChannel.EMAIL == "email"

    def test_channel_webhook(self):
        assert RoutingChannel.WEBHOOK == "webhook"

    def test_channel_sms(self):
        assert RoutingChannel.SMS == "sms"

    def test_channel_teams(self):
        assert RoutingChannel.TEAMS == "teams"

    # RoutingEffectiveness (4)
    def test_effectiveness_optimal(self):
        assert RoutingEffectiveness.OPTIMAL == "optimal"

    def test_effectiveness_adequate(self):
        assert RoutingEffectiveness.ADEQUATE == "adequate"

    def test_effectiveness_suboptimal(self):
        assert RoutingEffectiveness.SUBOPTIMAL == "suboptimal"

    def test_effectiveness_ineffective(self):
        assert RoutingEffectiveness.INEFFECTIVE == "ineffective"

    # ActionTaken (6)
    def test_action_acknowledged(self):
        assert ActionTaken.ACKNOWLEDGED == "acknowledged"

    def test_action_resolved(self):
        assert ActionTaken.RESOLVED == "resolved"

    def test_action_escalated(self):
        assert ActionTaken.ESCALATED == "escalated"

    def test_action_suppressed(self):
        assert ActionTaken.SUPPRESSED == "suppressed"

    def test_action_ignored(self):
        assert ActionTaken.IGNORED == "ignored"

    def test_action_reassigned(self):
        assert ActionTaken.REASSIGNED == "reassigned"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_routing_record_defaults(self):
        r = RoutingRecord()
        assert r.id
        assert r.alert_id == ""
        assert r.channel == RoutingChannel.SLACK
        assert r.action_taken == ActionTaken.ACKNOWLEDGED
        assert r.response_time_seconds == 0.0
        assert r.was_rerouted is False

    def test_routing_recommendation_defaults(self):
        rec = RoutingRecommendation()
        assert rec.id
        assert rec.current_channel == RoutingChannel.SLACK
        assert rec.recommended_channel == RoutingChannel.PAGERDUTY
        assert rec.effectiveness == RoutingEffectiveness.ADEQUATE
        assert rec.reason == ""

    def test_routing_analysis_report_defaults(self):
        report = RoutingAnalysisReport()
        assert report.total_routings == 0
        assert report.reroute_count == 0
        assert report.reroute_rate == 0.0
        assert report.ignored_count == 0
        assert report.ignored_rate == 0.0
        assert report.channel_effectiveness == {}
        assert report.team_effectiveness == {}
        assert report.recommendations == []


# ---------------------------------------------------------------------------
# record_routing
# ---------------------------------------------------------------------------


class TestRecordRouting:
    def test_basic_record(self):
        eng = _engine()
        r = eng.record_routing(
            alert_id="alert-1",
            alert_type="cpu_high",
            team="sre",
            channel=RoutingChannel.PAGERDUTY,
            action_taken=ActionTaken.RESOLVED,
            response_time_seconds=120.0,
        )
        assert r.alert_id == "alert-1"
        assert r.alert_type == "cpu_high"
        assert r.team == "sre"
        assert r.channel == RoutingChannel.PAGERDUTY
        assert r.action_taken == ActionTaken.RESOLVED

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for idx in range(5):
            eng.record_routing(alert_id=f"alert-{idx}", alert_type="test")
        assert len(eng._routings) == 3


# ---------------------------------------------------------------------------
# get_routing
# ---------------------------------------------------------------------------


class TestGetRouting:
    def test_found(self):
        eng = _engine()
        r = eng.record_routing(alert_id="a1", alert_type="disk_full")
        assert eng.get_routing(r.id) is not None
        assert eng.get_routing(r.id).alert_id == "a1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_routing("nonexistent") is None


# ---------------------------------------------------------------------------
# list_routings
# ---------------------------------------------------------------------------


class TestListRoutings:
    def test_list_all(self):
        eng = _engine()
        eng.record_routing(alert_id="a1", team="sre")
        eng.record_routing(alert_id="a2", team="platform")
        assert len(eng.list_routings()) == 2

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_routing(alert_id="a1", team="sre")
        eng.record_routing(alert_id="a2", team="platform")
        results = eng.list_routings(team="sre")
        assert len(results) == 1
        assert results[0].team == "sre"

    def test_filter_by_channel(self):
        eng = _engine()
        eng.record_routing(alert_id="a1", channel=RoutingChannel.SLACK)
        eng.record_routing(alert_id="a2", channel=RoutingChannel.PAGERDUTY)
        results = eng.list_routings(channel=RoutingChannel.PAGERDUTY)
        assert len(results) == 1
        assert results[0].channel == RoutingChannel.PAGERDUTY


# ---------------------------------------------------------------------------
# generate_recommendations
# ---------------------------------------------------------------------------


class TestGenerateRecommendations:
    def test_no_issues(self):
        eng = _engine()
        # All routings are fine — no reroutes, no ignores
        for _ in range(5):
            eng.record_routing(
                alert_type="healthy_alert",
                team="sre",
                action_taken=ActionTaken.RESOLVED,
                was_rerouted=False,
            )
        recs = eng.generate_recommendations()
        assert len(recs) == 0

    def test_with_reroute_pattern(self):
        eng = _engine(reroute_threshold=0.2)
        # 4 out of 5 rerouted (80%) => should trigger recommendation
        for idx in range(5):
            eng.record_routing(
                alert_type="flaky_alert",
                team="sre",
                channel=RoutingChannel.SLACK,
                was_rerouted=(idx < 4),
                action_taken=ActionTaken.ACKNOWLEDGED,
            )
        recs = eng.generate_recommendations()
        reroute_recs = [r for r in recs if "reroute" in r.reason.lower()]
        assert len(reroute_recs) >= 1
        assert reroute_recs[0].recommended_channel == RoutingChannel.PAGERDUTY

    def test_with_ignored_pattern(self):
        eng = _engine()
        # 4 out of 5 ignored (80%) => should trigger recommendation
        for idx in range(5):
            eng.record_routing(
                alert_type="noisy_alert",
                team="ops",
                action_taken=ActionTaken.IGNORED if idx < 4 else ActionTaken.RESOLVED,
            )
        recs = eng.generate_recommendations()
        ignored_recs = [r for r in recs if "ignored" in r.reason.lower()]
        assert len(ignored_recs) >= 1
        assert "escalation" in ignored_recs[0].recommended_team


# ---------------------------------------------------------------------------
# analyze_team_effectiveness
# ---------------------------------------------------------------------------


class TestAnalyzeTeamEffectiveness:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_team_effectiveness()
        assert result == {}

    def test_with_data(self):
        eng = _engine()
        eng.record_routing(team="sre", action_taken=ActionTaken.RESOLVED, response_time_seconds=60)
        eng.record_routing(team="sre", action_taken=ActionTaken.IGNORED, response_time_seconds=120)
        result = eng.analyze_team_effectiveness()
        assert "sre" in result
        assert result["sre"]["total_routings"] == 2
        assert result["sre"]["resolve_rate"] == 0.5
        assert result["sre"]["avg_response_time"] == 90.0


# ---------------------------------------------------------------------------
# detect_reroute_patterns
# ---------------------------------------------------------------------------


class TestDetectReroutePatterns:
    def test_none(self):
        eng = _engine(reroute_threshold=0.2)
        for _ in range(10):
            eng.record_routing(alert_type="stable", was_rerouted=False)
        patterns = eng.detect_reroute_patterns()
        assert len(patterns) == 0

    def test_with_patterns(self):
        eng = _engine(reroute_threshold=0.2)
        # 3 out of 5 rerouted (60%)
        for idx in range(5):
            eng.record_routing(
                alert_type="problematic",
                was_rerouted=(idx < 3),
            )
        patterns = eng.detect_reroute_patterns()
        assert len(patterns) == 1
        assert patterns[0]["alert_type"] == "problematic"
        assert patterns[0]["reroute_rate"] == 0.6


# ---------------------------------------------------------------------------
# compute_channel_effectiveness
# ---------------------------------------------------------------------------


class TestComputeChannelEffectiveness:
    def test_empty(self):
        eng = _engine()
        result = eng.compute_channel_effectiveness()
        assert result == {}

    def test_with_data(self):
        eng = _engine()
        eng.record_routing(channel=RoutingChannel.SLACK, action_taken=ActionTaken.RESOLVED)
        eng.record_routing(channel=RoutingChannel.SLACK, action_taken=ActionTaken.IGNORED)
        eng.record_routing(channel=RoutingChannel.PAGERDUTY, action_taken=ActionTaken.RESOLVED)
        result = eng.compute_channel_effectiveness()
        assert result["slack"] == 0.5  # 1 resolved out of 2
        assert result["pagerduty"] == 1.0  # 1 resolved out of 1


# ---------------------------------------------------------------------------
# identify_ignored_alerts
# ---------------------------------------------------------------------------


class TestIdentifyIgnoredAlerts:
    def test_none(self):
        eng = _engine()
        eng.record_routing(action_taken=ActionTaken.RESOLVED)
        assert len(eng.identify_ignored_alerts()) == 0

    def test_some_ignored(self):
        eng = _engine()
        eng.record_routing(alert_id="a1", action_taken=ActionTaken.IGNORED)
        eng.record_routing(alert_id="a2", action_taken=ActionTaken.RESOLVED)
        eng.record_routing(alert_id="a3", action_taken=ActionTaken.IGNORED)
        ignored = eng.identify_ignored_alerts()
        assert len(ignored) == 2
        assert all(r.action_taken == ActionTaken.IGNORED for r in ignored)


# ---------------------------------------------------------------------------
# generate_analysis_report
# ---------------------------------------------------------------------------


class TestGenerateAnalysisReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_routing(
            alert_type="cpu",
            team="sre",
            channel=RoutingChannel.SLACK,
            action_taken=ActionTaken.RESOLVED,
        )
        eng.record_routing(
            alert_type="disk",
            team="ops",
            channel=RoutingChannel.PAGERDUTY,
            action_taken=ActionTaken.IGNORED,
            was_rerouted=True,
        )
        report = eng.generate_analysis_report()
        assert report.total_routings == 2
        assert report.reroute_count == 1
        assert report.ignored_count == 1
        assert "slack" in report.channel_effectiveness
        assert "sre" in report.team_effectiveness


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine()
        eng.record_routing(alert_id="a1")
        # Force a recommendation to exist
        for _ in range(5):
            eng.record_routing(
                alert_type="noisy",
                was_rerouted=True,
            )
        eng.generate_recommendations()
        assert len(eng._routings) > 0
        assert len(eng._recommendations) > 0
        eng.clear_data()
        assert len(eng._routings) == 0
        assert len(eng._recommendations) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_routings"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["unique_alert_types"] == 0
        assert stats["unique_teams"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_routing(alert_type="cpu", team="sre")
        eng.record_routing(alert_type="disk", team="ops")
        stats = eng.get_stats()
        assert stats["total_routings"] == 2
        assert stats["unique_alert_types"] == 2
        assert stats["unique_teams"] == 2
        assert "cpu" in stats["alert_types"]
        assert "sre" in stats["teams"]
