"""Tests for shieldops.topology.cross_team_risk — CrossTeamDependencyRisk.

Covers:
- RiskLevel, DependencyDirection, CoordinationNeed enums
- CrossTeamDep, RiskAssessment, CrossTeamReport model defaults
- register_dependency (basic, unique IDs, extra fields, eviction)
- get_dependency (found, not found)
- list_dependencies (all, filter source, filter target, limit)
- assess_change_risk (basic, not found)
- calculate_blast_radius (basic, isolated)
- identify_critical_paths (found, none)
- detect_circular_dependencies (explicit, implicit, none)
- rank_teams_by_risk (basic, empty)
- generate_risk_report (populated, empty)
- clear_data (basic)
- get_stats (empty, populated)
"""

from __future__ import annotations

from shieldops.topology.cross_team_risk import (
    CoordinationNeed,
    CrossTeamDep,
    CrossTeamDependencyRisk,
    CrossTeamReport,
    DependencyDirection,
    RiskAssessment,
    RiskLevel,
)


def _engine(**kw) -> CrossTeamDependencyRisk:
    return CrossTeamDependencyRisk(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # RiskLevel (5 values)

    def test_risk_minimal(self):
        assert RiskLevel.MINIMAL == "minimal"

    def test_risk_low(self):
        assert RiskLevel.LOW == "low"

    def test_risk_moderate(self):
        assert RiskLevel.MODERATE == "moderate"

    def test_risk_high(self):
        assert RiskLevel.HIGH == "high"

    def test_risk_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    # DependencyDirection (5 values)

    def test_dir_upstream(self):
        assert DependencyDirection.UPSTREAM == "upstream"

    def test_dir_downstream(self):
        assert DependencyDirection.DOWNSTREAM == "downstream"

    def test_dir_bidirectional(self):
        assert DependencyDirection.BIDIRECTIONAL == "bidirectional"

    def test_dir_transitive(self):
        assert DependencyDirection.TRANSITIVE == "transitive"

    def test_dir_circular(self):
        assert DependencyDirection.CIRCULAR == "circular"

    # CoordinationNeed (5 values)

    def test_coord_none(self):
        assert CoordinationNeed.NONE == "none"

    def test_coord_notification(self):
        assert CoordinationNeed.NOTIFICATION == "notification"

    def test_coord_review_required(self):
        assert CoordinationNeed.REVIEW_REQUIRED == "review_required"

    def test_coord_joint_planning(self):
        assert CoordinationNeed.JOINT_PLANNING == "joint_planning"

    def test_coord_freeze_required(self):
        assert CoordinationNeed.FREEZE_REQUIRED == "freeze_required"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_cross_team_dep_defaults(self):
        d = CrossTeamDep(source_team="platform")
        assert d.id
        assert d.source_team == "platform"
        assert d.target_team == ""
        assert d.source_service == ""
        assert d.target_service == ""
        assert d.direction == (DependencyDirection.DOWNSTREAM)
        assert d.risk_level == RiskLevel.LOW
        assert d.coordination_need == (CoordinationNeed.NOTIFICATION)
        assert d.sla_impact_pct == 0.0
        assert d.created_at > 0

    def test_risk_assessment_defaults(self):
        a = RiskAssessment(dep_id="d-1")
        assert a.id
        assert a.dep_id == "d-1"
        assert a.change_description == ""
        assert a.blast_radius_teams == []
        assert a.risk_level == RiskLevel.LOW
        assert a.mitigation == ""
        assert a.assessed_by == ""
        assert a.created_at > 0

    def test_cross_team_report_defaults(self):
        r = CrossTeamReport()
        assert r.total_deps == 0
        assert r.total_assessments == 0
        assert r.high_risk_count == 0
        assert r.by_risk == {}
        assert r.by_direction == {}
        assert r.by_coordination == {}
        assert r.critical_paths == []
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# register_dependency
# -------------------------------------------------------------------


class TestRegisterDependency:
    def test_basic(self):
        e = _engine()
        d = e.register_dependency(
            source_team="platform",
            target_team="payments",
            source_service="api-gw",
            target_service="stripe-svc",
        )
        assert d.source_team == "platform"
        assert d.target_team == "payments"
        assert d.source_service == "api-gw"
        assert d.target_service == "stripe-svc"

    def test_unique_ids(self):
        e = _engine()
        d1 = e.register_dependency(source_team="a")
        d2 = e.register_dependency(source_team="b")
        assert d1.id != d2.id

    def test_extra_fields(self):
        e = _engine()
        d = e.register_dependency(
            source_team="infra",
            target_team="data",
            direction=DependencyDirection.BIDIRECTIONAL,
            risk_level=RiskLevel.HIGH,
            coordination_need=(CoordinationNeed.JOINT_PLANNING),
            sla_impact_pct=75.0,
        )
        assert d.direction == (DependencyDirection.BIDIRECTIONAL)
        assert d.risk_level == RiskLevel.HIGH
        assert d.coordination_need == (CoordinationNeed.JOINT_PLANNING)
        assert d.sla_impact_pct == 75.0

    def test_evicts_at_max(self):
        e = _engine(max_deps=2)
        d1 = e.register_dependency(source_team="a")
        e.register_dependency(source_team="b")
        e.register_dependency(source_team="c")
        deps = e.list_dependencies()
        ids = {d.id for d in deps}
        assert d1.id not in ids
        assert len(deps) == 2


# -------------------------------------------------------------------
# get_dependency
# -------------------------------------------------------------------


class TestGetDependency:
    def test_found(self):
        e = _engine()
        d = e.register_dependency(
            source_team="platform",
        )
        assert e.get_dependency(d.id) is not None
        assert e.get_dependency(d.id).source_team == "platform"

    def test_not_found(self):
        e = _engine()
        assert e.get_dependency("nope") is None


# -------------------------------------------------------------------
# list_dependencies
# -------------------------------------------------------------------


class TestListDependencies:
    def test_list_all(self):
        e = _engine()
        e.register_dependency(source_team="a")
        e.register_dependency(source_team="b")
        e.register_dependency(source_team="c")
        assert len(e.list_dependencies()) == 3

    def test_filter_by_source_team(self):
        e = _engine()
        e.register_dependency(source_team="alpha")
        e.register_dependency(source_team="beta")
        filtered = e.list_dependencies(
            source_team="alpha",
        )
        assert len(filtered) == 1
        assert filtered[0].source_team == "alpha"

    def test_filter_by_target_team(self):
        e = _engine()
        e.register_dependency(target_team="ops")
        e.register_dependency(target_team="dev")
        filtered = e.list_dependencies(
            target_team="ops",
        )
        assert len(filtered) == 1

    def test_limit(self):
        e = _engine()
        for i in range(10):
            e.register_dependency(
                source_team=f"t-{i}",
            )
        assert len(e.list_dependencies(limit=3)) == 3


# -------------------------------------------------------------------
# assess_change_risk
# -------------------------------------------------------------------


class TestAssessChangeRisk:
    def test_basic(self):
        e = _engine()
        d = e.register_dependency(
            source_team="platform",
            target_team="payments",
            risk_level=RiskLevel.HIGH,
        )
        a = e.assess_change_risk(
            dep_id=d.id,
            change_description="Upgrade API v2",
            assessed_by="alice",
        )
        assert a is not None
        assert a.dep_id == d.id
        assert a.change_description == "Upgrade API v2"
        assert a.assessed_by == "alice"
        assert len(a.blast_radius_teams) >= 2
        assert a.mitigation != ""

    def test_not_found(self):
        e = _engine()
        assert e.assess_change_risk("bad-id") is None


# -------------------------------------------------------------------
# calculate_blast_radius
# -------------------------------------------------------------------


class TestCalculateBlastRadius:
    def test_basic(self):
        e = _engine()
        e.register_dependency(
            source_team="platform",
            target_team="payments",
        )
        e.register_dependency(
            source_team="platform",
            target_team="billing",
        )
        result = e.calculate_blast_radius("platform")
        assert result["team"] == "platform"
        assert "payments" in result["affected_teams"]
        assert "billing" in result["affected_teams"]
        assert result["affected_count"] == 2

    def test_isolated(self):
        e = _engine()
        e.register_dependency(
            source_team="alpha",
            target_team="beta",
        )
        result = e.calculate_blast_radius("gamma")
        assert result["affected_count"] == 0


# -------------------------------------------------------------------
# identify_critical_paths
# -------------------------------------------------------------------


class TestIdentifyCriticalPaths:
    def test_found(self):
        e = _engine()
        e.register_dependency(
            source_team="a",
            target_team="b",
            risk_level=RiskLevel.CRITICAL,
            sla_impact_pct=95.0,
        )
        e.register_dependency(
            source_team="c",
            target_team="d",
            risk_level=RiskLevel.LOW,
        )
        paths = e.identify_critical_paths()
        assert len(paths) == 1
        assert paths[0]["risk_level"] == "critical"

    def test_none(self):
        e = _engine()
        e.register_dependency(
            risk_level=RiskLevel.LOW,
        )
        assert e.identify_critical_paths() == []


# -------------------------------------------------------------------
# detect_circular_dependencies
# -------------------------------------------------------------------


class TestDetectCircularDependencies:
    def test_explicit_circular(self):
        e = _engine()
        e.register_dependency(
            source_team="a",
            target_team="b",
            direction=DependencyDirection.CIRCULAR,
        )
        circular = e.detect_circular_dependencies()
        assert len(circular) >= 1

    def test_implicit_circular(self):
        e = _engine()
        e.register_dependency(
            source_team="x",
            target_team="y",
        )
        e.register_dependency(
            source_team="y",
            target_team="x",
        )
        circular = e.detect_circular_dependencies()
        assert len(circular) >= 1

    def test_none(self):
        e = _engine()
        e.register_dependency(
            source_team="a",
            target_team="b",
        )
        assert e.detect_circular_dependencies() == []


# -------------------------------------------------------------------
# rank_teams_by_risk
# -------------------------------------------------------------------


class TestRankTeamsByRisk:
    def test_basic(self):
        e = _engine()
        e.register_dependency(
            source_team="alpha",
            target_team="beta",
            risk_level=RiskLevel.CRITICAL,
        )
        e.register_dependency(
            source_team="gamma",
            target_team="delta",
            risk_level=RiskLevel.LOW,
        )
        ranked = e.rank_teams_by_risk()
        assert len(ranked) >= 2
        assert ranked[0]["risk_score"] >= (ranked[-1]["risk_score"])

    def test_empty(self):
        e = _engine()
        assert e.rank_teams_by_risk() == []


# -------------------------------------------------------------------
# generate_risk_report
# -------------------------------------------------------------------


class TestGenerateRiskReport:
    def test_populated(self):
        e = _engine()
        d = e.register_dependency(
            source_team="platform",
            target_team="payments",
            risk_level=RiskLevel.HIGH,
            direction=DependencyDirection.DOWNSTREAM,
            coordination_need=(CoordinationNeed.JOINT_PLANNING),
        )
        e.register_dependency(
            source_team="infra",
            target_team="data",
            risk_level=RiskLevel.LOW,
        )
        e.assess_change_risk(
            d.id,
            change_description="migrate db",
        )
        report = e.generate_risk_report()
        assert report.total_deps == 2
        assert report.total_assessments == 1
        assert report.high_risk_count == 1
        assert "high" in report.by_risk
        assert "downstream" in report.by_direction
        assert len(report.recommendations) > 0

    def test_empty(self):
        e = _engine()
        report = e.generate_risk_report()
        assert report.total_deps == 0
        assert report.total_assessments == 0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_basic(self):
        e = _engine()
        e.register_dependency(source_team="a")
        e.register_dependency(source_team="b")
        d = e.register_dependency(source_team="c")
        e.assess_change_risk(d.id, assessed_by="x")
        count = e.clear_data()
        assert count == 3
        assert e.list_dependencies() == []


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        e = _engine()
        stats = e.get_stats()
        assert stats["total_deps"] == 0
        assert stats["total_assessments"] == 0
        assert stats["max_deps"] == 100000
        assert stats["critical_risk_threshold"] == 0.8
        assert stats["risk_distribution"] == {}

    def test_populated(self):
        e = _engine()
        e.register_dependency(
            source_team="a",
            risk_level=RiskLevel.HIGH,
        )
        e.register_dependency(
            source_team="b",
            risk_level=RiskLevel.LOW,
        )
        d = e.register_dependency(
            source_team="c",
            risk_level=RiskLevel.HIGH,
        )
        e.assess_change_risk(d.id, assessed_by="y")
        stats = e.get_stats()
        assert stats["total_deps"] == 3
        assert stats["total_assessments"] == 1
        assert stats["risk_distribution"]["high"] == 2
        assert stats["risk_distribution"]["low"] == 1
