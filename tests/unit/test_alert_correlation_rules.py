"""Tests for shieldops.observability.alert_correlation_rules — AlertCorrelationRuleEngine."""

from __future__ import annotations

from shieldops.observability.alert_correlation_rules import (
    AlertCorrelationRuleEngine,
    CorrelationAction,
    CorrelationMatch,
    CorrelationReport,
    CorrelationRule,
    RuleStatus,
    RuleType,
)


def _engine(**kw) -> AlertCorrelationRuleEngine:
    return AlertCorrelationRuleEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # RuleType (5)
    def test_type_temporal(self):
        assert RuleType.TEMPORAL == "temporal"

    def test_type_causal(self):
        assert RuleType.CAUSAL == "causal"

    def test_type_topological(self):
        assert RuleType.TOPOLOGICAL == "topological"

    def test_type_threshold(self):
        assert RuleType.THRESHOLD == "threshold"

    def test_type_composite(self):
        assert RuleType.COMPOSITE == "composite"

    # CorrelationAction (5)
    def test_action_suppress(self):
        assert CorrelationAction.SUPPRESS == "suppress"

    def test_action_merge(self):
        assert CorrelationAction.MERGE == "merge"

    def test_action_escalate(self):
        assert CorrelationAction.ESCALATE == "escalate"

    def test_action_reroute(self):
        assert CorrelationAction.REROUTE == "reroute"

    def test_action_annotate(self):
        assert CorrelationAction.ANNOTATE == "annotate"

    # RuleStatus (5)
    def test_status_active(self):
        assert RuleStatus.ACTIVE == "active"

    def test_status_disabled(self):
        assert RuleStatus.DISABLED == "disabled"

    def test_status_testing(self):
        assert RuleStatus.TESTING == "testing"

    def test_status_expired(self):
        assert RuleStatus.EXPIRED == "expired"

    def test_status_archived(self):
        assert RuleStatus.ARCHIVED == "archived"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_correlation_rule_defaults(self):
        r = CorrelationRule()
        assert r.id
        assert r.name == ""
        assert r.rule_type == RuleType.TEMPORAL
        assert r.action == CorrelationAction.SUPPRESS
        assert r.status == RuleStatus.ACTIVE
        assert r.source_pattern == ""
        assert r.time_window_seconds == 300
        assert r.match_count == 0
        assert r.suppress_count == 0

    def test_correlation_match_defaults(self):
        m = CorrelationMatch()
        assert m.id
        assert m.rule_id == ""
        assert m.source_alert == ""
        assert m.action_taken == CorrelationAction.SUPPRESS

    def test_correlation_report_defaults(self):
        r = CorrelationReport()
        assert r.total_rules == 0
        assert r.active_rules == 0
        assert r.suppression_rate == 0.0
        assert r.top_rules == []
        assert r.recommendations == []


# ---------------------------------------------------------------------------
# register_rule
# ---------------------------------------------------------------------------


class TestRegisterRule:
    def test_basic_register(self):
        eng = _engine()
        r = eng.register_rule(
            name="CPU cascade",
            rule_type=RuleType.CAUSAL,
            action=CorrelationAction.SUPPRESS,
            source_pattern="cpu_high",
        )
        assert r.name == "CPU cascade"
        assert r.rule_type == RuleType.CAUSAL
        assert r.action == CorrelationAction.SUPPRESS

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.register_rule("rule-a", RuleType.TEMPORAL, CorrelationAction.MERGE)
        r2 = eng.register_rule("rule-b", RuleType.TEMPORAL, CorrelationAction.MERGE)
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_rules=3)
        for i in range(5):
            eng.register_rule(f"rule-{i}", RuleType.TEMPORAL, CorrelationAction.SUPPRESS)
        assert len(eng._rules) == 3


# ---------------------------------------------------------------------------
# get_rule
# ---------------------------------------------------------------------------


class TestGetRule:
    def test_found(self):
        eng = _engine()
        r = eng.register_rule("test", RuleType.TEMPORAL, CorrelationAction.SUPPRESS)
        assert eng.get_rule(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_rule("nonexistent") is None


# ---------------------------------------------------------------------------
# list_rules
# ---------------------------------------------------------------------------


class TestListRules:
    def test_list_all(self):
        eng = _engine()
        eng.register_rule("r1", RuleType.TEMPORAL, CorrelationAction.SUPPRESS)
        eng.register_rule("r2", RuleType.CAUSAL, CorrelationAction.MERGE)
        assert len(eng.list_rules()) == 2

    def test_filter_rule_type(self):
        eng = _engine()
        eng.register_rule("r1", RuleType.TEMPORAL, CorrelationAction.SUPPRESS)
        eng.register_rule("r2", RuleType.CAUSAL, CorrelationAction.MERGE)
        results = eng.list_rules(rule_type=RuleType.CAUSAL)
        assert len(results) == 1
        assert results[0].rule_type == RuleType.CAUSAL

    def test_filter_action(self):
        eng = _engine()
        eng.register_rule("r1", RuleType.TEMPORAL, CorrelationAction.SUPPRESS)
        eng.register_rule("r2", RuleType.TEMPORAL, CorrelationAction.ESCALATE)
        results = eng.list_rules(action=CorrelationAction.ESCALATE)
        assert len(results) == 1
        assert results[0].action == CorrelationAction.ESCALATE

    def test_filter_status(self):
        eng = _engine()
        eng.register_rule("r1", RuleType.TEMPORAL, CorrelationAction.SUPPRESS)
        rule2 = eng.register_rule("r2", RuleType.TEMPORAL, CorrelationAction.SUPPRESS)
        rule2.status = RuleStatus.DISABLED
        results = eng.list_rules(status=RuleStatus.ACTIVE)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# evaluate_alert
# ---------------------------------------------------------------------------


class TestEvaluateAlert:
    def test_no_match(self):
        eng = _engine()
        eng.register_rule(
            "test",
            RuleType.TEMPORAL,
            CorrelationAction.SUPPRESS,
            source_pattern="disk_full",
        )
        matches = eng.evaluate_alert("cpu_high")
        assert len(matches) == 0

    def test_match_on_alert_name(self):
        eng = _engine()
        eng.register_rule(
            "cpu rule",
            RuleType.TEMPORAL,
            CorrelationAction.SUPPRESS,
            source_pattern="cpu",
        )
        matches = eng.evaluate_alert("cpu_high_alert")
        assert len(matches) == 1
        assert matches[0].source_alert == "cpu_high_alert"

    def test_match_on_alert_source(self):
        eng = _engine()
        eng.register_rule(
            "prod rule",
            RuleType.TEMPORAL,
            CorrelationAction.SUPPRESS,
            source_pattern="prod-cluster",
        )
        matches = eng.evaluate_alert("memory_alert", alert_source="prod-cluster-01")
        assert len(matches) == 1

    def test_suppress_increments_count(self):
        eng = _engine()
        rule = eng.register_rule(
            "test",
            RuleType.TEMPORAL,
            CorrelationAction.SUPPRESS,
            source_pattern="cpu",
        )
        eng.evaluate_alert("cpu_high")
        assert rule.match_count == 1
        assert rule.suppress_count == 1

    def test_non_suppress_no_suppress_count(self):
        eng = _engine()
        rule = eng.register_rule(
            "test",
            RuleType.TEMPORAL,
            CorrelationAction.ESCALATE,
            source_pattern="cpu",
        )
        eng.evaluate_alert("cpu_high")
        assert rule.match_count == 1
        assert rule.suppress_count == 0

    def test_disabled_rule_skipped(self):
        eng = _engine()
        rule = eng.register_rule(
            "test",
            RuleType.TEMPORAL,
            CorrelationAction.SUPPRESS,
            source_pattern="cpu",
        )
        rule.status = RuleStatus.DISABLED
        matches = eng.evaluate_alert("cpu_high")
        assert len(matches) == 0


# ---------------------------------------------------------------------------
# find_correlated_alerts
# ---------------------------------------------------------------------------


class TestFindCorrelatedAlerts:
    def test_no_matches(self):
        eng = _engine()
        assert eng.find_correlated_alerts("cpu") == []

    def test_with_matches(self):
        eng = _engine()
        eng.register_rule(
            "test",
            RuleType.TEMPORAL,
            CorrelationAction.SUPPRESS,
            source_pattern="cpu",
            target_pattern="memory_overload",
        )
        eng.evaluate_alert("cpu_high")
        results = eng.find_correlated_alerts("cpu")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# calculate_suppression_rate
# ---------------------------------------------------------------------------


class TestCalculateSuppressionRate:
    def test_no_data(self):
        eng = _engine()
        result = eng.calculate_suppression_rate()
        assert result["total_matches"] == 0
        assert result["suppression_rate_pct"] == 0.0

    def test_with_data(self):
        eng = _engine()
        eng.register_rule(
            "suppress-rule",
            RuleType.TEMPORAL,
            CorrelationAction.SUPPRESS,
            source_pattern="cpu",
        )
        eng.register_rule(
            "escalate-rule",
            RuleType.TEMPORAL,
            CorrelationAction.ESCALATE,
            source_pattern="cpu",
        )
        eng.evaluate_alert("cpu_alert")
        result = eng.calculate_suppression_rate()
        assert result["total_matches"] == 2
        assert result["total_suppressions"] == 1
        assert result["suppression_rate_pct"] == 50.0


# ---------------------------------------------------------------------------
# detect_rule_conflicts
# ---------------------------------------------------------------------------


class TestDetectRuleConflicts:
    def test_no_conflicts(self):
        eng = _engine()
        eng.register_rule("r1", RuleType.TEMPORAL, CorrelationAction.SUPPRESS, source_pattern="cpu")
        eng.register_rule("r2", RuleType.TEMPORAL, CorrelationAction.SUPPRESS, source_pattern="cpu")
        conflicts = eng.detect_rule_conflicts()
        assert len(conflicts) == 0  # Same action => no conflict

    def test_with_conflict(self):
        eng = _engine()
        eng.register_rule("r1", RuleType.TEMPORAL, CorrelationAction.SUPPRESS, source_pattern="cpu")
        eng.register_rule("r2", RuleType.TEMPORAL, CorrelationAction.ESCALATE, source_pattern="cpu")
        conflicts = eng.detect_rule_conflicts()
        assert len(conflicts) == 1
        assert "conflict_reason" in conflicts[0]


# ---------------------------------------------------------------------------
# rank_rules_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankRulesByEffectiveness:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_rules_by_effectiveness() == []

    def test_sorted_by_match_count(self):
        eng = _engine()
        eng.register_rule(
            "low", RuleType.TEMPORAL, CorrelationAction.SUPPRESS, source_pattern="low"
        )
        eng.register_rule(
            "high", RuleType.TEMPORAL, CorrelationAction.SUPPRESS, source_pattern="high"
        )
        # Trigger matches for r2
        eng.evaluate_alert("high_cpu")
        eng.evaluate_alert("high_mem")
        eng.evaluate_alert("low_disk")
        ranked = eng.rank_rules_by_effectiveness()
        assert ranked[0].name == "high"
        assert ranked[0].match_count == 2


# ---------------------------------------------------------------------------
# generate_correlation_report
# ---------------------------------------------------------------------------


class TestGenerateCorrelationReport:
    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_correlation_report()
        assert report.total_rules == 0
        assert report.total_matches == 0

    def test_with_data(self):
        eng = _engine()
        eng.register_rule(
            "r1",
            RuleType.TEMPORAL,
            CorrelationAction.SUPPRESS,
            source_pattern="cpu",
        )
        eng.evaluate_alert("cpu_high")
        report = eng.generate_correlation_report()
        assert report.total_rules == 1
        assert report.active_rules == 1
        assert report.total_matches == 1
        assert report.total_suppressions == 1


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.register_rule("test", RuleType.TEMPORAL, CorrelationAction.SUPPRESS, source_pattern="x")
        eng.evaluate_alert("x_alert")
        eng.clear_data()
        assert len(eng._rules) == 0
        assert len(eng._matches) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_rules"] == 0
        assert stats["total_matches"] == 0

    def test_populated(self):
        eng = _engine()
        eng.register_rule(
            "r1",
            RuleType.TEMPORAL,
            CorrelationAction.SUPPRESS,
            source_pattern="cpu",
        )
        eng.evaluate_alert("cpu_high")
        stats = eng.get_stats()
        assert stats["total_rules"] == 1
        assert stats["total_matches"] == 1
        assert RuleType.TEMPORAL in stats["type_distribution"]
        assert CorrelationAction.SUPPRESS in stats["action_distribution"]
