"""Tests for shieldops.changes.deployment_impact."""

from __future__ import annotations

from shieldops.changes.deployment_impact import (
    DeploymentImpactAnalyzer,
    DeploymentImpactReport,
    ImpactRecord,
    ImpactRule,
    ImpactScope,
    ImpactSeverity,
    ImpactType,
)


def _engine(**kw) -> DeploymentImpactAnalyzer:
    return DeploymentImpactAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ImpactScope (5)
    def test_scope_single_service(self):
        assert ImpactScope.SINGLE_SERVICE == "single_service"

    def test_scope_service_group(self):
        assert ImpactScope.SERVICE_GROUP == "service_group"

    def test_scope_availability_zone(self):
        assert ImpactScope.AVAILABILITY_ZONE == "availability_zone"

    def test_scope_region(self):
        assert ImpactScope.REGION == "region"

    def test_scope_global(self):
        assert ImpactScope.GLOBAL == "global"

    # ImpactType (5)
    def test_type_performance(self):
        assert ImpactType.PERFORMANCE == "performance"

    def test_type_availability(self):
        assert ImpactType.AVAILABILITY == "availability"

    def test_type_error_rate(self):
        assert ImpactType.ERROR_RATE == "error_rate"

    def test_type_latency(self):
        assert ImpactType.LATENCY == "latency"

    def test_type_resource_usage(self):
        assert ImpactType.RESOURCE_USAGE == "resource_usage"

    # ImpactSeverity (5)
    def test_severity_critical(self):
        assert ImpactSeverity.CRITICAL == "critical"

    def test_severity_major(self):
        assert ImpactSeverity.MAJOR == "major"

    def test_severity_moderate(self):
        assert ImpactSeverity.MODERATE == "moderate"

    def test_severity_minor(self):
        assert ImpactSeverity.MINOR == "minor"

    def test_severity_none(self):
        assert ImpactSeverity.NONE == "none"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_impact_record_defaults(self):
        r = ImpactRecord()
        assert r.id
        assert r.deployment_name == ""
        assert r.scope == ImpactScope.SINGLE_SERVICE
        assert r.impact_type == ImpactType.PERFORMANCE
        assert r.severity == ImpactSeverity.MINOR
        assert r.impact_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_impact_rule_defaults(self):
        r = ImpactRule()
        assert r.id
        assert r.rule_name == ""
        assert r.scope == ImpactScope.SINGLE_SERVICE
        assert r.impact_type == ImpactType.PERFORMANCE
        assert r.max_impact_score == 50.0
        assert r.auto_rollback is False
        assert r.created_at > 0

    def test_impact_report_defaults(self):
        r = DeploymentImpactReport()
        assert r.total_impacts == 0
        assert r.total_rules == 0
        assert r.low_impact_rate_pct == 0.0
        assert r.by_scope == {}
        assert r.by_severity == {}
        assert r.critical_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_impact
# -------------------------------------------------------------------


class TestRecordImpact:
    def test_basic(self):
        eng = _engine()
        r = eng.record_impact(
            "deploy-v1",
            scope=ImpactScope.SINGLE_SERVICE,
            severity=ImpactSeverity.MINOR,
        )
        assert r.deployment_name == "deploy-v1"
        assert r.scope == ImpactScope.SINGLE_SERVICE

    def test_with_impact_type(self):
        eng = _engine()
        r = eng.record_impact(
            "deploy-v2",
            impact_type=ImpactType.LATENCY,
        )
        assert r.impact_type == ImpactType.LATENCY

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_impact(f"deploy-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_impact
# -------------------------------------------------------------------


class TestGetImpact:
    def test_found(self):
        eng = _engine()
        r = eng.record_impact("deploy-v1")
        assert eng.get_impact(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_impact("nonexistent") is None


# -------------------------------------------------------------------
# list_impacts
# -------------------------------------------------------------------


class TestListImpacts:
    def test_list_all(self):
        eng = _engine()
        eng.record_impact("deploy-v1")
        eng.record_impact("deploy-v2")
        assert len(eng.list_impacts()) == 2

    def test_filter_by_deployment(self):
        eng = _engine()
        eng.record_impact("deploy-v1")
        eng.record_impact("deploy-v2")
        results = eng.list_impacts(deployment_name="deploy-v1")
        assert len(results) == 1

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_impact(
            "deploy-v1",
            scope=ImpactScope.REGION,
        )
        eng.record_impact(
            "deploy-v2",
            scope=ImpactScope.GLOBAL,
        )
        results = eng.list_impacts(scope=ImpactScope.REGION)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        p = eng.add_rule(
            "critical-guard",
            scope=ImpactScope.SINGLE_SERVICE,
            impact_type=ImpactType.PERFORMANCE,
            max_impact_score=30.0,
            auto_rollback=True,
        )
        assert p.rule_name == "critical-guard"
        assert p.max_impact_score == 30.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._policies) == 2


# -------------------------------------------------------------------
# analyze_impact_trends
# -------------------------------------------------------------------


class TestAnalyzeImpactTrends:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact(
            "deploy-v1",
            severity=ImpactSeverity.MINOR,
            impact_score=20.0,
        )
        eng.record_impact(
            "deploy-v1",
            severity=ImpactSeverity.CRITICAL,
            impact_score=80.0,
        )
        result = eng.analyze_impact_trends("deploy-v1")
        assert result["deployment_name"] == "deploy-v1"
        assert result["impact_count"] == 2
        assert result["low_rate"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_impact_trends("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(max_impact_score=100.0)
        eng.record_impact(
            "deploy-v1",
            severity=ImpactSeverity.MINOR,
            impact_score=20.0,
        )
        result = eng.analyze_impact_trends("deploy-v1")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_high_impact_deployments
# -------------------------------------------------------------------


class TestIdentifyHighImpactDeployments:
    def test_with_high_impact(self):
        eng = _engine()
        eng.record_impact(
            "deploy-v1",
            severity=ImpactSeverity.CRITICAL,
        )
        eng.record_impact(
            "deploy-v1",
            severity=ImpactSeverity.CRITICAL,
        )
        eng.record_impact(
            "deploy-v2",
            severity=ImpactSeverity.MINOR,
        )
        results = eng.identify_high_impact_deployments()
        assert len(results) == 1
        assert results[0]["deployment_name"] == "deploy-v1"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_deployments() == []


# -------------------------------------------------------------------
# rank_by_impact_score
# -------------------------------------------------------------------


class TestRankByImpactScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact("deploy-v1", impact_score=90.0)
        eng.record_impact("deploy-v1", impact_score=90.0)
        eng.record_impact("deploy-v2", impact_score=5.0)
        results = eng.rank_by_impact_score()
        assert results[0]["deployment_name"] == "deploy-v1"
        assert results[0]["avg_impact_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_score() == []


# -------------------------------------------------------------------
# detect_impact_patterns
# -------------------------------------------------------------------


class TestDetectImpactPatterns:
    def test_with_patterns(self):
        eng = _engine()
        for _ in range(5):
            eng.record_impact(
                "deploy-v1",
                severity=ImpactSeverity.CRITICAL,
            )
        eng.record_impact(
            "deploy-v2",
            severity=ImpactSeverity.MINOR,
        )
        results = eng.detect_impact_patterns()
        assert len(results) == 1
        assert results[0]["deployment_name"] == "deploy-v1"
        assert results[0]["pattern_detected"] is True

    def test_no_patterns(self):
        eng = _engine()
        eng.record_impact(
            "deploy-v1",
            severity=ImpactSeverity.MAJOR,
        )
        assert eng.detect_impact_patterns() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact(
            "deploy-v1",
            severity=ImpactSeverity.MINOR,
        )
        eng.record_impact(
            "deploy-v2",
            severity=ImpactSeverity.CRITICAL,
        )
        eng.record_impact(
            "deploy-v2",
            severity=ImpactSeverity.CRITICAL,
        )
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_impacts == 3
        assert report.total_rules == 1
        assert report.by_scope != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_impacts == 0
        assert "healthy" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_impact("deploy-v1")
        eng.add_rule("rule-1")
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
        assert stats["total_impacts"] == 0
        assert stats["total_rules"] == 0
        assert stats["scope_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_impact(
            "deploy-v1",
            scope=ImpactScope.SINGLE_SERVICE,
        )
        eng.record_impact(
            "deploy-v2",
            scope=ImpactScope.REGION,
        )
        eng.add_rule("r1")
        stats = eng.get_stats()
        assert stats["total_impacts"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_deployments"] == 2
