"""Tests for shieldops.observability.alert_tuning_feedback — AlertTuningFeedbackLoop."""

from __future__ import annotations

from shieldops.observability.alert_tuning_feedback import (
    AlertFeedback,
    AlertFeedbackRecord,
    AlertRuleEffectiveness,
    AlertTuningFeedbackLoop,
    AlertTuningReport,
    RuleHealth,
    TuningAction,
)


def _engine(**kw) -> AlertTuningFeedbackLoop:
    return AlertTuningFeedbackLoop(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # AlertFeedback (5)
    def test_feedback_actionable(self):
        assert AlertFeedback.ACTIONABLE == "actionable"

    def test_feedback_informational(self):
        assert AlertFeedback.INFORMATIONAL == "informational"

    def test_feedback_noisy(self):
        assert AlertFeedback.NOISY == "noisy"

    def test_feedback_duplicate(self):
        assert AlertFeedback.DUPLICATE == "duplicate"

    def test_feedback_missed_incident(self):
        assert AlertFeedback.MISSED_INCIDENT == "missed_incident"

    # TuningAction (5)
    def test_action_tighten_threshold(self):
        assert TuningAction.TIGHTEN_THRESHOLD == "tighten_threshold"

    def test_action_relax_threshold(self):
        assert TuningAction.RELAX_THRESHOLD == "relax_threshold"

    def test_action_add_filter(self):
        assert TuningAction.ADD_FILTER == "add_filter"

    def test_action_disable_rule(self):
        assert TuningAction.DISABLE_RULE == "disable_rule"

    def test_action_no_change(self):
        assert TuningAction.NO_CHANGE == "no_change"

    # RuleHealth (5)
    def test_health_excellent(self):
        assert RuleHealth.EXCELLENT == "excellent"

    def test_health_good(self):
        assert RuleHealth.GOOD == "good"

    def test_health_needs_tuning(self):
        assert RuleHealth.NEEDS_TUNING == "needs_tuning"

    def test_health_poor(self):
        assert RuleHealth.POOR == "poor"

    def test_health_broken(self):
        assert RuleHealth.BROKEN == "broken"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_alert_feedback_record_defaults(self):
        r = AlertFeedbackRecord()
        assert r.id
        assert r.rule_name == ""
        assert r.alert_id == ""
        assert r.feedback == AlertFeedback.ACTIONABLE
        assert r.responder_id == ""
        assert r.comment == ""
        assert r.created_at > 0

    def test_alert_rule_effectiveness_defaults(self):
        e = AlertRuleEffectiveness()
        assert e.id
        assert e.rule_name == ""
        assert e.total_alerts == 0
        assert e.actionable_count == 0
        assert e.noisy_count == 0
        assert e.duplicate_count == 0
        assert e.precision_pct == 0.0
        assert e.health == RuleHealth.GOOD
        assert e.recommended_action == TuningAction.NO_CHANGE
        assert e.created_at > 0

    def test_alert_tuning_report_defaults(self):
        r = AlertTuningReport()
        assert r.total_feedback == 0
        assert r.total_rules_evaluated == 0
        assert r.avg_precision_pct == 0.0
        assert r.noisy_rule_count == 0
        assert r.by_feedback == {}
        assert r.by_health == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_feedback
# ---------------------------------------------------------------------------


class TestRecordFeedback:
    def test_basic(self):
        eng = _engine()
        r = eng.record_feedback(rule_name="cpu-alert")
        assert r.rule_name == "cpu-alert"
        assert r.feedback == AlertFeedback.ACTIONABLE

    def test_with_params(self):
        eng = _engine()
        r = eng.record_feedback(
            rule_name="disk-alert",
            alert_id="alert-123",
            feedback=AlertFeedback.NOISY,
            responder_id="ops-1",
            comment="too sensitive",
        )
        assert r.alert_id == "alert-123"
        assert r.feedback == AlertFeedback.NOISY
        assert r.responder_id == "ops-1"
        assert r.comment == "too sensitive"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_feedback(rule_name=f"rule-{i}")
        assert len(eng._feedback) == 3


# ---------------------------------------------------------------------------
# get_feedback
# ---------------------------------------------------------------------------


class TestGetFeedback:
    def test_found(self):
        eng = _engine()
        r = eng.record_feedback(rule_name="cpu-alert")
        result = eng.get_feedback(r.id)
        assert result is not None
        assert result.rule_name == "cpu-alert"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_feedback("nonexistent") is None


# ---------------------------------------------------------------------------
# list_feedback
# ---------------------------------------------------------------------------


class TestListFeedback:
    def test_list_all(self):
        eng = _engine()
        eng.record_feedback(rule_name="cpu-alert")
        eng.record_feedback(rule_name="disk-alert")
        assert len(eng.list_feedback()) == 2

    def test_filter_by_rule_name(self):
        eng = _engine()
        eng.record_feedback(rule_name="cpu-alert")
        eng.record_feedback(rule_name="disk-alert")
        results = eng.list_feedback(rule_name="cpu-alert")
        assert len(results) == 1
        assert results[0].rule_name == "cpu-alert"

    def test_filter_by_feedback(self):
        eng = _engine()
        eng.record_feedback(rule_name="cpu-alert", feedback=AlertFeedback.ACTIONABLE)
        eng.record_feedback(rule_name="disk-alert", feedback=AlertFeedback.NOISY)
        results = eng.list_feedback(feedback=AlertFeedback.NOISY)
        assert len(results) == 1
        assert results[0].feedback == AlertFeedback.NOISY


# ---------------------------------------------------------------------------
# evaluate_rule_effectiveness
# ---------------------------------------------------------------------------


class TestEvaluateRuleEffectiveness:
    def test_with_feedback(self):
        eng = _engine()
        eng.record_feedback(rule_name="cpu-alert", feedback=AlertFeedback.ACTIONABLE)
        eng.record_feedback(rule_name="cpu-alert", feedback=AlertFeedback.ACTIONABLE)
        eng.record_feedback(rule_name="cpu-alert", feedback=AlertFeedback.NOISY)
        eff = eng.evaluate_rule_effectiveness("cpu-alert")
        assert eff.rule_name == "cpu-alert"
        assert eff.total_alerts == 3
        assert eff.actionable_count == 2
        assert eff.noisy_count == 1
        assert eff.precision_pct == 66.67
        assert eff.health == RuleHealth.NEEDS_TUNING

    def test_no_feedback(self):
        eng = _engine()
        eff = eng.evaluate_rule_effectiveness("unknown-rule")
        assert eff.rule_name == "unknown-rule"
        assert eff.total_alerts == 0
        assert eff.health == RuleHealth.GOOD
        assert eff.recommended_action == TuningAction.NO_CHANGE

    def test_all_noisy(self):
        eng = _engine()
        eng.record_feedback(rule_name="bad-rule", feedback=AlertFeedback.NOISY)
        eng.record_feedback(rule_name="bad-rule", feedback=AlertFeedback.NOISY)
        eff = eng.evaluate_rule_effectiveness("bad-rule")
        assert eff.precision_pct == 0.0
        assert eff.health == RuleHealth.BROKEN
        assert eff.recommended_action == TuningAction.DISABLE_RULE


# ---------------------------------------------------------------------------
# identify_noisy_rules
# ---------------------------------------------------------------------------


class TestIdentifyNoisyRules:
    def test_has_noisy(self):
        eng = _engine(precision_threshold=70.0)
        # rule-a: 1 actionable, 3 noisy => noise_rate 75%
        eng.record_feedback(rule_name="rule-a", feedback=AlertFeedback.ACTIONABLE)
        eng.record_feedback(rule_name="rule-a", feedback=AlertFeedback.NOISY)
        eng.record_feedback(rule_name="rule-a", feedback=AlertFeedback.NOISY)
        eng.record_feedback(rule_name="rule-a", feedback=AlertFeedback.NOISY)
        # rule-b: all actionable => noise_rate 0%
        eng.record_feedback(rule_name="rule-b", feedback=AlertFeedback.ACTIONABLE)
        results = eng.identify_noisy_rules()
        assert len(results) == 1
        assert results[0]["rule_name"] == "rule-a"
        assert results[0]["noise_rate_pct"] == 75.0

    def test_no_noisy(self):
        eng = _engine(precision_threshold=70.0)
        eng.record_feedback(rule_name="good-rule", feedback=AlertFeedback.ACTIONABLE)
        assert eng.identify_noisy_rules() == []


# ---------------------------------------------------------------------------
# identify_blind_spots
# ---------------------------------------------------------------------------


class TestIdentifyBlindSpots:
    def test_has_missed(self):
        eng = _engine()
        eng.record_feedback(rule_name="cpu-alert", feedback=AlertFeedback.MISSED_INCIDENT)
        eng.record_feedback(rule_name="cpu-alert", feedback=AlertFeedback.MISSED_INCIDENT)
        eng.record_feedback(rule_name="disk-alert", feedback=AlertFeedback.ACTIONABLE)
        results = eng.identify_blind_spots()
        assert len(results) == 1
        assert results[0]["rule_name"] == "cpu-alert"
        assert results[0]["missed_count"] == 2

    def test_no_missed(self):
        eng = _engine()
        eng.record_feedback(rule_name="rule-a", feedback=AlertFeedback.ACTIONABLE)
        assert eng.identify_blind_spots() == []


# ---------------------------------------------------------------------------
# recommend_tuning_actions
# ---------------------------------------------------------------------------


class TestRecommendTuningActions:
    def test_has_recommendations(self):
        eng = _engine()
        # All noisy => BROKEN => DISABLE_RULE
        eng.record_feedback(rule_name="bad-rule", feedback=AlertFeedback.NOISY)
        eng.record_feedback(rule_name="bad-rule", feedback=AlertFeedback.NOISY)
        results = eng.recommend_tuning_actions()
        assert len(results) >= 1
        assert results[0]["rule_name"] == "bad-rule"
        assert results[0]["recommended_action"] == TuningAction.DISABLE_RULE.value

    def test_no_recommendations(self):
        eng = _engine()
        eng.record_feedback(rule_name="good-rule", feedback=AlertFeedback.ACTIONABLE)
        results = eng.recommend_tuning_actions()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# calculate_rule_health
# ---------------------------------------------------------------------------


class TestCalculateRuleHealth:
    def test_healthy_rule(self):
        eng = _engine()
        eng.record_feedback(rule_name="cpu-alert", feedback=AlertFeedback.ACTIONABLE)
        result = eng.calculate_rule_health("cpu-alert")
        assert result["rule_name"] == "cpu-alert"
        assert result["health"] == RuleHealth.EXCELLENT.value
        assert result["precision_pct"] == 100.0
        assert result["total_alerts"] == 1

    def test_unhealthy_rule(self):
        eng = _engine()
        eng.record_feedback(rule_name="noisy-rule", feedback=AlertFeedback.NOISY)
        result = eng.calculate_rule_health("noisy-rule")
        assert result["health"] == RuleHealth.BROKEN.value
        assert result["precision_pct"] == 0.0


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_feedback(rule_name="cpu-alert", feedback=AlertFeedback.ACTIONABLE)
        eng.record_feedback(rule_name="disk-alert", feedback=AlertFeedback.NOISY)
        report = eng.generate_report()
        assert isinstance(report, AlertTuningReport)
        assert report.total_feedback == 2
        assert report.total_rules_evaluated == 2
        assert len(report.by_feedback) > 0
        assert len(report.by_health) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine(precision_threshold=0.0)
        report = eng.generate_report()
        assert report.total_feedback == 0
        assert report.total_rules_evaluated == 0
        assert "Alert rules performing within acceptable parameters" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_feedback(rule_name="cpu-alert")
        eng.evaluate_rule_effectiveness("cpu-alert")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._feedback) == 0
        assert len(eng._effectiveness) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_feedback"] == 0
        assert stats["total_effectiveness"] == 0
        assert stats["feedback_distribution"] == {}
        assert stats["unique_rules"] == 0

    def test_populated(self):
        eng = _engine(precision_threshold=70.0)
        eng.record_feedback(rule_name="cpu-alert", feedback=AlertFeedback.ACTIONABLE)
        eng.evaluate_rule_effectiveness("cpu-alert")
        stats = eng.get_stats()
        assert stats["total_feedback"] == 1
        assert stats["total_effectiveness"] == 1
        assert stats["precision_threshold"] == 70.0
        assert "actionable" in stats["feedback_distribution"]
        assert stats["unique_rules"] == 1
