"""Tests for alert_routing_optimizer — AlertRoutingOptimizer."""

from __future__ import annotations

from shieldops.observability.alert_routing_optimizer import (
    AlertPriority,
    AlertRoutingOptimizer,
    AlertRoutingReport,
    RoutingOutcome,
    RoutingPolicy,
    RoutingRecord,
    RoutingStrategy,
)


def _engine(**kw) -> AlertRoutingOptimizer:
    return AlertRoutingOptimizer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # RoutingStrategy (5)
    def test_strategy_round_robin(self):
        assert RoutingStrategy.ROUND_ROBIN == "round_robin"

    def test_strategy_skill_based(self):
        assert RoutingStrategy.SKILL_BASED == "skill_based"

    def test_strategy_load_balanced(self):
        assert RoutingStrategy.LOAD_BALANCED == "load_balanced"

    def test_strategy_escalation_chain(self):
        assert RoutingStrategy.ESCALATION_CHAIN == "escalation_chain"

    def test_strategy_geographic(self):
        assert RoutingStrategy.GEOGRAPHIC == "geographic"

    # RoutingOutcome (5)
    def test_outcome_acknowledged(self):
        assert RoutingOutcome.ACKNOWLEDGED == "acknowledged"

    def test_outcome_escalated(self):
        assert RoutingOutcome.ESCALATED == "escalated"

    def test_outcome_suppressed(self):
        assert RoutingOutcome.SUPPRESSED == "suppressed"

    def test_outcome_misrouted(self):
        assert RoutingOutcome.MISROUTED == "misrouted"

    def test_outcome_ignored(self):
        assert RoutingOutcome.IGNORED == "ignored"

    # AlertPriority (5)
    def test_priority_page(self):
        assert AlertPriority.PAGE == "page"

    def test_priority_high(self):
        assert AlertPriority.HIGH == "high"

    def test_priority_medium(self):
        assert AlertPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert AlertPriority.LOW == "low"

    def test_priority_informational(self):
        assert AlertPriority.INFORMATIONAL == "informational"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_routing_record_defaults(self):
        r = RoutingRecord()
        assert r.id
        assert r.alert_name == ""
        assert r.strategy == RoutingStrategy.SKILL_BASED
        assert r.outcome == RoutingOutcome.ACKNOWLEDGED
        assert r.priority == AlertPriority.MEDIUM
        assert r.response_time_seconds == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_routing_policy_defaults(self):
        r = RoutingPolicy()
        assert r.id
        assert r.policy_name == ""
        assert r.strategy == RoutingStrategy.SKILL_BASED
        assert r.priority == AlertPriority.MEDIUM
        assert r.max_response_seconds == 300.0
        assert r.auto_escalate is True
        assert r.created_at > 0

    def test_alert_routing_report_defaults(self):
        r = AlertRoutingReport()
        assert r.total_routings == 0
        assert r.total_policies == 0
        assert r.ack_rate_pct == 0.0
        assert r.by_strategy == {}
        assert r.by_outcome == {}
        assert r.misrouted_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_routing
# -------------------------------------------------------------------


class TestRecordRouting:
    def test_basic(self):
        eng = _engine()
        r = eng.record_routing(
            "cpu-alert",
            strategy=RoutingStrategy.ROUND_ROBIN,
            outcome=RoutingOutcome.ACKNOWLEDGED,
        )
        assert r.alert_name == "cpu-alert"
        assert r.strategy == RoutingStrategy.ROUND_ROBIN

    def test_with_priority(self):
        eng = _engine()
        r = eng.record_routing(
            "mem-alert",
            priority=AlertPriority.PAGE,
        )
        assert r.priority == AlertPriority.PAGE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_routing(f"alert-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_routing
# -------------------------------------------------------------------


class TestGetRouting:
    def test_found(self):
        eng = _engine()
        r = eng.record_routing("cpu-alert")
        assert eng.get_routing(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_routing("nonexistent") is None


# -------------------------------------------------------------------
# list_routings
# -------------------------------------------------------------------


class TestListRoutings:
    def test_list_all(self):
        eng = _engine()
        eng.record_routing("alert-a")
        eng.record_routing("alert-b")
        assert len(eng.list_routings()) == 2

    def test_filter_by_alert_name(self):
        eng = _engine()
        eng.record_routing("alert-a")
        eng.record_routing("alert-b")
        results = eng.list_routings(alert_name="alert-a")
        assert len(results) == 1

    def test_filter_by_strategy(self):
        eng = _engine()
        eng.record_routing(
            "alert-a",
            strategy=RoutingStrategy.GEOGRAPHIC,
        )
        eng.record_routing(
            "alert-b",
            strategy=RoutingStrategy.ROUND_ROBIN,
        )
        results = eng.list_routings(strategy=RoutingStrategy.GEOGRAPHIC)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_policy
# -------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            "escalate-pages",
            strategy=RoutingStrategy.ESCALATION_CHAIN,
            priority=AlertPriority.PAGE,
            max_response_seconds=60.0,
            auto_escalate=True,
        )
        assert p.policy_name == "escalate-pages"
        assert p.max_response_seconds == 60.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_policy(f"policy-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_routing_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeRoutingEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_routing(
            "alert-a",
            outcome=RoutingOutcome.ACKNOWLEDGED,
        )
        eng.record_routing(
            "alert-a",
            outcome=RoutingOutcome.MISROUTED,
        )
        result = eng.analyze_routing_effectiveness("alert-a")
        assert result["alert_name"] == "alert-a"
        assert result["routing_count"] == 2
        assert result["ack_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_routing_effectiveness("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_misrouted_alerts
# -------------------------------------------------------------------


class TestIdentifyMisroutedAlerts:
    def test_with_misrouted(self):
        eng = _engine()
        eng.record_routing(
            "alert-a",
            outcome=RoutingOutcome.MISROUTED,
        )
        eng.record_routing(
            "alert-a",
            outcome=RoutingOutcome.MISROUTED,
        )
        eng.record_routing(
            "alert-b",
            outcome=RoutingOutcome.ACKNOWLEDGED,
        )
        results = eng.identify_misrouted_alerts()
        assert len(results) == 1
        assert results[0]["alert_name"] == "alert-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_misrouted_alerts() == []


# -------------------------------------------------------------------
# rank_by_response_time
# -------------------------------------------------------------------


class TestRankByResponseTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_routing("alert-a", response_time_seconds=100.0)
        eng.record_routing("alert-a", response_time_seconds=200.0)
        eng.record_routing("alert-b", response_time_seconds=50.0)
        results = eng.rank_by_response_time()
        assert results[0]["alert_name"] == "alert-a"
        assert results[0]["avg_response_time"] == 150.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_response_time() == []


# -------------------------------------------------------------------
# detect_routing_issues
# -------------------------------------------------------------------


class TestDetectRoutingIssues:
    def test_with_issues(self):
        eng = _engine()
        for _ in range(5):
            eng.record_routing(
                "alert-a",
                outcome=RoutingOutcome.MISROUTED,
            )
        eng.record_routing(
            "alert-b",
            outcome=RoutingOutcome.ACKNOWLEDGED,
        )
        results = eng.detect_routing_issues()
        assert len(results) == 1
        assert results[0]["alert_name"] == "alert-a"
        assert results[0]["issue_detected"] is True

    def test_no_issues(self):
        eng = _engine()
        eng.record_routing(
            "alert-a",
            outcome=RoutingOutcome.MISROUTED,
        )
        assert eng.detect_routing_issues() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_routing(
            "alert-a",
            outcome=RoutingOutcome.ACKNOWLEDGED,
        )
        eng.record_routing(
            "alert-b",
            outcome=RoutingOutcome.MISROUTED,
        )
        eng.record_routing(
            "alert-b",
            outcome=RoutingOutcome.MISROUTED,
        )
        eng.add_policy("policy-1")
        report = eng.generate_report()
        assert report.total_routings == 3
        assert report.total_policies == 1
        assert report.by_strategy != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_routings == 0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_routing("alert-a")
        eng.add_policy("policy-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._policies) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_routings"] == 0
        assert stats["total_policies"] == 0
        assert stats["strategy_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_routing(
            "alert-a",
            strategy=RoutingStrategy.ROUND_ROBIN,
        )
        eng.record_routing(
            "alert-b",
            strategy=RoutingStrategy.GEOGRAPHIC,
        )
        eng.add_policy("p1")
        stats = eng.get_stats()
        assert stats["total_routings"] == 2
        assert stats["total_policies"] == 1
        assert stats["unique_alerts"] == 2
