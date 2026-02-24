"""Tests for shieldops.analytics.team_performance — TeamPerformanceAnalyzer."""

from __future__ import annotations

from shieldops.analytics.team_performance import (
    PerformanceMetric,
    PerformanceReport,
    RiskAssessment,
    RiskCategory,
    TeamHealth,
    TeamMember,
    TeamPerformanceAnalyzer,
)


def _engine(**kw) -> TeamPerformanceAnalyzer:
    return TeamPerformanceAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_metric_mttr(self):
        assert PerformanceMetric.MTTR == "mttr"

    def test_metric_participation(self):
        assert PerformanceMetric.INCIDENT_PARTICIPATION == "incident_participation"

    def test_metric_breadth(self):
        assert PerformanceMetric.KNOWLEDGE_BREADTH == "knowledge_breadth"

    def test_metric_oncall(self):
        assert PerformanceMetric.ONCALL_LOAD == "oncall_load"

    def test_metric_quality(self):
        assert PerformanceMetric.RESOLUTION_QUALITY == "resolution_quality"

    def test_risk_burnout(self):
        assert RiskCategory.BURNOUT == "burnout"

    def test_risk_silo(self):
        assert RiskCategory.KNOWLEDGE_SILO == "knowledge_silo"

    def test_risk_understaffing(self):
        assert RiskCategory.UNDERSTAFFING == "understaffing"

    def test_risk_skill_gap(self):
        assert RiskCategory.SKILL_GAP == "skill_gap"

    def test_risk_attrition(self):
        assert RiskCategory.ATTRITION == "attrition"

    def test_health_healthy(self):
        assert TeamHealth.HEALTHY == "healthy"

    def test_health_at_risk(self):
        assert TeamHealth.AT_RISK == "at_risk"

    def test_health_critical(self):
        assert TeamHealth.CRITICAL == "critical"

    def test_health_unknown(self):
        assert TeamHealth.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_member_defaults(self):
        m = TeamMember()
        assert m.id
        assert m.oncall_hours == 0.0
        assert m.incidents_handled == 0

    def test_report_defaults(self):
        r = PerformanceReport()
        assert r.total_incidents == 0
        assert r.participation_score == 0.0

    def test_assessment_defaults(self):
        a = RiskAssessment()
        assert a.risk_category == RiskCategory.BURNOUT
        assert a.risk_score == 0.0


# ---------------------------------------------------------------------------
# register_member
# ---------------------------------------------------------------------------


class TestRegisterMember:
    def test_basic_register(self):
        eng = _engine()
        m = eng.register_member("Alice", team="platform")
        assert m.name == "Alice"
        assert m.team == "platform"

    def test_unique_ids(self):
        eng = _engine()
        m1 = eng.register_member("Alice")
        m2 = eng.register_member("Bob")
        assert m1.id != m2.id

    def test_eviction_at_max(self):
        eng = _engine(max_members=3)
        for i in range(5):
            eng.register_member(f"member-{i}")
        assert len(eng._members) == 3

    def test_with_skills(self):
        eng = _engine()
        m = eng.register_member("Alice", skills=["k8s", "aws"])
        assert len(m.skills) == 2


# ---------------------------------------------------------------------------
# get / list members
# ---------------------------------------------------------------------------


class TestGetMember:
    def test_found(self):
        eng = _engine()
        m = eng.register_member("Alice")
        assert eng.get_member(m.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_member("nonexistent") is None


class TestListMembers:
    def test_list_all(self):
        eng = _engine()
        eng.register_member("Alice", team="a")
        eng.register_member("Bob", team="b")
        assert len(eng.list_members()) == 2

    def test_filter_by_team(self):
        eng = _engine()
        eng.register_member("Alice", team="a")
        eng.register_member("Bob", team="b")
        results = eng.list_members(team="a")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# record_activity
# ---------------------------------------------------------------------------


class TestRecordActivity:
    def test_basic_activity(self):
        eng = _engine()
        m = eng.register_member("Alice")
        result = eng.record_activity(m.id, oncall_hours=8.0)
        assert result["oncall_hours"] == 8.0

    def test_incident_resolved(self):
        eng = _engine()
        m = eng.register_member("Alice")
        eng.record_activity(m.id, duration_minutes=30.0, incident_resolved=True)
        assert m.incidents_handled == 1
        assert m.avg_resolution_minutes == 30.0

    def test_invalid_member(self):
        eng = _engine()
        result = eng.record_activity("bad_id")
        assert result.get("error") == "member_not_found"


# ---------------------------------------------------------------------------
# compute_performance
# ---------------------------------------------------------------------------


class TestComputePerformance:
    def test_basic_performance(self):
        eng = _engine()
        m = eng.register_member("Alice", team="platform")
        eng.record_activity(m.id, duration_minutes=30.0, incident_resolved=True)
        report = eng.compute_performance("platform")
        assert report.total_incidents == 1
        assert report.participation_score == 1.0

    def test_empty_team(self):
        eng = _engine()
        report = eng.compute_performance("empty")
        assert report.total_incidents == 0


# ---------------------------------------------------------------------------
# detect_knowledge_silos
# ---------------------------------------------------------------------------


class TestKnowledgeSilos:
    def test_silo_detected(self):
        eng = _engine()
        eng.register_member("Alice", team="platform", skills=["unique_skill"])
        eng.register_member("Bob", team="platform", skills=["common"])
        silos = eng.detect_knowledge_silos(team="platform")
        silo_skills = [s.description for s in silos]
        assert any("unique_skill" in d for d in silo_skills)

    def test_no_silos(self):
        eng = _engine()
        eng.register_member("Alice", team="platform", skills=["k8s"])
        eng.register_member("Bob", team="platform", skills=["k8s"])
        silos = eng.detect_knowledge_silos(team="platform")
        assert len(silos) == 0


# ---------------------------------------------------------------------------
# assess_burnout_risk
# ---------------------------------------------------------------------------


class TestBurnoutRisk:
    def test_burnout_detected(self):
        eng = _engine(burnout_threshold=0.5)
        m1 = eng.register_member("Alice", team="platform")
        m2 = eng.register_member("Bob", team="platform")
        m1.oncall_hours = 200.0
        m2.oncall_hours = 10.0
        risks = eng.assess_burnout_risk(team="platform")
        assert len(risks) >= 1

    def test_no_burnout(self):
        eng = _engine()
        eng.register_member("Alice", team="platform")
        eng.register_member("Bob", team="platform")
        risks = eng.assess_burnout_risk(team="platform")
        assert len(risks) == 0


# ---------------------------------------------------------------------------
# team health / recommendations / stats
# ---------------------------------------------------------------------------


class TestTeamHealth:
    def test_unknown_team(self):
        eng = _engine()
        health = eng.get_team_health("nonexistent")
        assert health["health"] == TeamHealth.UNKNOWN

    def test_healthy_team(self):
        eng = _engine()
        eng.register_member("Alice", team="platform", skills=["k8s"])
        eng.register_member("Bob", team="platform", skills=["k8s"])
        health = eng.get_team_health("platform")
        assert health["health"] == TeamHealth.HEALTHY


class TestRecommendations:
    def test_recommendations(self):
        eng = _engine(burnout_threshold=0.5)
        m1 = eng.register_member("Alice", team="platform", skills=["unique"])
        eng.register_member("Bob", team="platform", skills=["common"])
        m1.oncall_hours = 200.0
        recs = eng.get_recommendations("platform")
        assert len(recs) >= 1


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_members"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.register_member("Alice", team="platform")
        eng.register_member("Bob", team="infra")
        stats = eng.get_stats()
        assert stats["total_members"] == 2
        assert stats["unique_teams"] == 2
