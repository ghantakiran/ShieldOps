"""Tests for toil_quantifier — TeamToilQuantifier."""

from __future__ import annotations

from shieldops.operations.toil_quantifier import (
    AutomationPotential,
    TeamToilQuantifier,
    ToilCategory,
    ToilImpact,
    ToilPolicy,
    ToilQuantifierReport,
    ToilRecord,
)


def _engine(**kw) -> TeamToilQuantifier:
    return TeamToilQuantifier(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ToilCategory (5)
    def test_category_manual_deployment(self):
        assert ToilCategory.MANUAL_DEPLOYMENT == "manual_deployment"

    def test_category_alert_handling(self):
        assert ToilCategory.ALERT_HANDLING == "alert_handling"

    def test_category_ticket_triage(self):
        assert ToilCategory.TICKET_TRIAGE == "ticket_triage"

    def test_category_config_management(self):
        assert ToilCategory.CONFIG_MANAGEMENT == "config_management"

    def test_category_reporting(self):
        assert ToilCategory.REPORTING == "reporting"

    # ToilImpact (5)
    def test_impact_severe(self):
        assert ToilImpact.SEVERE == "severe"

    def test_impact_high(self):
        assert ToilImpact.HIGH == "high"

    def test_impact_moderate(self):
        assert ToilImpact.MODERATE == "moderate"

    def test_impact_low(self):
        assert ToilImpact.LOW == "low"

    def test_impact_minimal(self):
        assert ToilImpact.MINIMAL == "minimal"

    # AutomationPotential (5)
    def test_potential_fully(self):
        assert AutomationPotential.FULLY_AUTOMATABLE == "fully_automatable"

    def test_potential_mostly(self):
        assert AutomationPotential.MOSTLY_AUTOMATABLE == "mostly_automatable"

    def test_potential_partially(self):
        assert AutomationPotential.PARTIALLY_AUTOMATABLE == "partially_automatable"

    def test_potential_difficult(self):
        assert AutomationPotential.DIFFICULT == "difficult"

    def test_potential_not_automatable(self):
        assert AutomationPotential.NOT_AUTOMATABLE == "not_automatable"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_toil_record_defaults(self):
        r = ToilRecord()
        assert r.id
        assert r.team_name == ""
        assert r.category == ToilCategory.MANUAL_DEPLOYMENT
        assert r.impact == ToilImpact.MODERATE
        assert r.potential == AutomationPotential.PARTIALLY_AUTOMATABLE
        assert r.hours_spent == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_toil_policy_defaults(self):
        r = ToilPolicy()
        assert r.id
        assert r.policy_name == ""
        assert r.category == ToilCategory.MANUAL_DEPLOYMENT
        assert r.impact == ToilImpact.MODERATE
        assert r.max_toil_hours_weekly == 10.0
        assert r.automation_target_pct == 50.0
        assert r.created_at > 0

    def test_toil_quantifier_report_defaults(self):
        r = ToilQuantifierReport()
        assert r.total_records == 0
        assert r.total_policies == 0
        assert r.low_toil_rate_pct == 0.0
        assert r.by_category == {}
        assert r.by_impact == {}
        assert r.severe_toil_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_toil
# -------------------------------------------------------------------


class TestRecordToil:
    def test_basic(self):
        eng = _engine()
        r = eng.record_toil(
            "team-alpha",
            category=ToilCategory.ALERT_HANDLING,
            impact=ToilImpact.HIGH,
        )
        assert r.team_name == "team-alpha"
        assert r.category == ToilCategory.ALERT_HANDLING

    def test_with_potential(self):
        eng = _engine()
        r = eng.record_toil(
            "team-beta",
            potential=(AutomationPotential.FULLY_AUTOMATABLE),
        )
        assert r.potential == AutomationPotential.FULLY_AUTOMATABLE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_toil(f"team-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_toil
# -------------------------------------------------------------------


class TestGetToil:
    def test_found(self):
        eng = _engine()
        r = eng.record_toil("team-alpha")
        assert eng.get_toil(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_toil("nonexistent") is None


# -------------------------------------------------------------------
# list_toils
# -------------------------------------------------------------------


class TestListToils:
    def test_list_all(self):
        eng = _engine()
        eng.record_toil("team-a")
        eng.record_toil("team-b")
        assert len(eng.list_toils()) == 2

    def test_filter_by_team_name(self):
        eng = _engine()
        eng.record_toil("team-a")
        eng.record_toil("team-b")
        results = eng.list_toils(team_name="team-a")
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_toil(
            "team-a",
            category=ToilCategory.REPORTING,
        )
        eng.record_toil(
            "team-b",
            category=ToilCategory.TICKET_TRIAGE,
        )
        results = eng.list_toils(category=ToilCategory.REPORTING)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_policy
# -------------------------------------------------------------------


class TestAddPolicy:
    def test_basic(self):
        eng = _engine()
        p = eng.add_policy(
            "reduce-deploys",
            category=ToilCategory.MANUAL_DEPLOYMENT,
            impact=ToilImpact.HIGH,
            max_toil_hours_weekly=5.0,
            automation_target_pct=80.0,
        )
        assert p.policy_name == "reduce-deploys"
        assert p.max_toil_hours_weekly == 5.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_policy(f"policy-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_toil_burden
# -------------------------------------------------------------------


class TestAnalyzeToilBurden:
    def test_with_data(self):
        eng = _engine()
        eng.record_toil("team-a", impact=ToilImpact.LOW)
        eng.record_toil("team-a", impact=ToilImpact.SEVERE)
        result = eng.analyze_toil_burden("team-a")
        assert result["team_name"] == "team-a"
        assert result["toil_count"] == 2
        assert result["low_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_toil_burden("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_high_toil_teams
# -------------------------------------------------------------------


class TestIdentifyHighToilTeams:
    def test_with_high_toil(self):
        eng = _engine()
        eng.record_toil("team-a", impact=ToilImpact.SEVERE)
        eng.record_toil("team-a", impact=ToilImpact.SEVERE)
        eng.record_toil("team-b", impact=ToilImpact.LOW)
        results = eng.identify_high_toil_teams()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_toil_teams() == []


# -------------------------------------------------------------------
# rank_by_hours_spent
# -------------------------------------------------------------------


class TestRankByHoursSpent:
    def test_with_data(self):
        eng = _engine()
        eng.record_toil("team-a", hours_spent=20.0)
        eng.record_toil("team-a", hours_spent=10.0)
        eng.record_toil("team-b", hours_spent=5.0)
        results = eng.rank_by_hours_spent()
        assert results[0]["team_name"] == "team-a"
        assert results[0]["avg_hours_spent"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_hours_spent() == []


# -------------------------------------------------------------------
# detect_toil_patterns
# -------------------------------------------------------------------


class TestDetectToilPatterns:
    def test_with_patterns(self):
        eng = _engine()
        for _ in range(5):
            eng.record_toil(
                "team-a",
                impact=ToilImpact.SEVERE,
            )
        eng.record_toil("team-b", impact=ToilImpact.LOW)
        results = eng.detect_toil_patterns()
        assert len(results) == 1
        assert results[0]["team_name"] == "team-a"
        assert results[0]["pattern_detected"] is True

    def test_no_patterns(self):
        eng = _engine()
        eng.record_toil("team-a", impact=ToilImpact.SEVERE)
        assert eng.detect_toil_patterns() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_toil("team-a", impact=ToilImpact.LOW)
        eng.record_toil("team-b", impact=ToilImpact.SEVERE)
        eng.record_toil("team-b", impact=ToilImpact.SEVERE)
        eng.add_policy("policy-1")
        report = eng.generate_report()
        assert report.total_records == 3
        assert report.total_policies == 1
        assert report.by_category != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_toil("team-a")
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
        assert stats["total_records"] == 0
        assert stats["total_policies"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_toil(
            "team-a",
            category=ToilCategory.ALERT_HANDLING,
        )
        eng.record_toil(
            "team-b",
            category=ToilCategory.REPORTING,
        )
        eng.add_policy("p1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_policies"] == 1
        assert stats["unique_teams"] == 2
