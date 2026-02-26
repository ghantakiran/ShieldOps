"""Tests for shieldops.compliance.policy_impact — PolicyImpactScorer."""

from __future__ import annotations

from shieldops.compliance.policy_impact import (
    ImpactScope,
    ImpactSeverity,
    PolicyConflict,
    PolicyDomain,
    PolicyImpactRecord,
    PolicyImpactReport,
    PolicyImpactScorer,
)


def _engine(**kw) -> PolicyImpactScorer:
    return PolicyImpactScorer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # PolicyDomain (5)
    def test_domain_security(self):
        assert PolicyDomain.SECURITY == "security"

    def test_domain_compliance(self):
        assert PolicyDomain.COMPLIANCE == "compliance"

    def test_domain_operational(self):
        assert PolicyDomain.OPERATIONAL == "operational"

    def test_domain_financial(self):
        assert PolicyDomain.FINANCIAL == "financial"

    def test_domain_access_control(self):
        assert PolicyDomain.ACCESS_CONTROL == "access_control"

    # ImpactSeverity (5)
    def test_sev_critical(self):
        assert ImpactSeverity.CRITICAL == "critical"

    def test_sev_high(self):
        assert ImpactSeverity.HIGH == "high"

    def test_sev_medium(self):
        assert ImpactSeverity.MEDIUM == "medium"

    def test_sev_low(self):
        assert ImpactSeverity.LOW == "low"

    def test_sev_negligible(self):
        assert ImpactSeverity.NEGLIGIBLE == "negligible"

    # ImpactScope (5)
    def test_scope_org_wide(self):
        assert ImpactScope.ORGANIZATION_WIDE == "organization_wide"

    def test_scope_department(self):
        assert ImpactScope.DEPARTMENT == "department"

    def test_scope_team(self):
        assert ImpactScope.TEAM == "team"

    def test_scope_service(self):
        assert ImpactScope.SERVICE == "service"

    def test_scope_individual(self):
        assert ImpactScope.INDIVIDUAL == "individual"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_impact_record_defaults(self):
        r = PolicyImpactRecord()
        assert r.id
        assert r.policy_name == ""
        assert r.domain == PolicyDomain.SECURITY
        assert r.severity == ImpactSeverity.MEDIUM
        assert r.scope == ImpactScope.SERVICE
        assert r.affected_services_count == 0
        assert r.risk_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_policy_conflict_defaults(self):
        r = PolicyConflict()
        assert r.id
        assert r.policy_a == ""
        assert r.policy_b == ""
        assert r.conflict_type == ""
        assert r.severity == ImpactSeverity.MEDIUM
        assert r.resolution == ""
        assert r.created_at > 0

    def test_impact_report_defaults(self):
        r = PolicyImpactReport()
        assert r.total_impacts == 0
        assert r.total_conflicts == 0
        assert r.avg_risk_score == 0.0
        assert r.by_domain == {}
        assert r.by_severity == {}
        assert r.high_impact_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_impact
# -------------------------------------------------------------------


class TestRecordImpact:
    def test_basic(self):
        eng = _engine()
        r = eng.record_impact("policy-x", risk_score=95.0)
        assert r.policy_name == "policy-x"
        assert r.severity == ImpactSeverity.CRITICAL

    def test_auto_severity_high(self):
        eng = _engine()
        r = eng.record_impact("policy-y", risk_score=75.0)
        assert r.severity == ImpactSeverity.HIGH

    def test_auto_severity_low(self):
        eng = _engine()
        r = eng.record_impact("policy-z", risk_score=35.0)
        assert r.severity == ImpactSeverity.LOW

    def test_explicit_severity(self):
        eng = _engine()
        r = eng.record_impact("policy-a", severity=ImpactSeverity.NEGLIGIBLE)
        assert r.severity == ImpactSeverity.NEGLIGIBLE

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_impact(f"policy-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_impact
# -------------------------------------------------------------------


class TestGetImpact:
    def test_found(self):
        eng = _engine()
        r = eng.record_impact("policy-x")
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
        eng.record_impact("policy-a")
        eng.record_impact("policy-b")
        assert len(eng.list_impacts()) == 2

    def test_filter_by_policy(self):
        eng = _engine()
        eng.record_impact("policy-a")
        eng.record_impact("policy-b")
        results = eng.list_impacts(policy_name="policy-a")
        assert len(results) == 1

    def test_filter_by_domain(self):
        eng = _engine()
        eng.record_impact("p1", domain=PolicyDomain.SECURITY)
        eng.record_impact("p2", domain=PolicyDomain.FINANCIAL)
        results = eng.list_impacts(domain=PolicyDomain.SECURITY)
        assert len(results) == 1


# -------------------------------------------------------------------
# record_conflict
# -------------------------------------------------------------------


class TestRecordConflict:
    def test_basic(self):
        eng = _engine()
        c = eng.record_conflict(
            "policy-a",
            "policy-b",
            conflict_type="overlap",
            severity=ImpactSeverity.HIGH,
            resolution="merge policies",
        )
        assert c.policy_a == "policy-a"
        assert c.conflict_type == "overlap"

    def test_eviction_at_max(self):
        eng = _engine(max_conflict_count=2)
        for i in range(4):
            eng.record_conflict(f"a-{i}", f"b-{i}")
        assert len(eng._conflicts) == 2


# -------------------------------------------------------------------
# analyze_policy_impact
# -------------------------------------------------------------------


class TestAnalyzePolicyImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact(
            "policy-x",
            domain=PolicyDomain.SECURITY,
            risk_score=85.0,
        )
        result = eng.analyze_policy_impact("policy-x")
        assert result["policy_name"] == "policy-x"
        assert result["domain"] == "security"

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_policy_impact("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_high_impact_policies
# -------------------------------------------------------------------


class TestIdentifyHighImpactPolicies:
    def test_with_high(self):
        eng = _engine()
        eng.record_impact("p1", risk_score=95.0)
        eng.record_impact("p2", risk_score=20.0)
        results = eng.identify_high_impact_policies()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_policies() == []


# -------------------------------------------------------------------
# rank_by_affected_scope
# -------------------------------------------------------------------


class TestRankByAffectedScope:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact("p1", affected_services_count=10)
        eng.record_impact("p2", affected_services_count=50)
        results = eng.rank_by_affected_scope()
        assert results[0]["affected_services_count"] == 50

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_affected_scope() == []


# -------------------------------------------------------------------
# detect_policy_conflicts
# -------------------------------------------------------------------


class TestDetectPolicyConflicts:
    def test_with_conflicts(self):
        eng = _engine()
        eng.record_conflict("a", "b", conflict_type="overlap")
        results = eng.detect_policy_conflicts()
        assert len(results) == 1
        assert results[0]["conflict_type"] == "overlap"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_policy_conflicts() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact("p1", risk_score=95.0)
        eng.record_impact("p2", risk_score=20.0)
        eng.record_conflict("p1", "p2")
        report = eng.generate_report()
        assert report.total_impacts == 2
        assert report.total_conflicts == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_impacts == 0
        assert "acceptable" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_impact("p1")
        eng.record_conflict("a", "b")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._conflicts) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_impacts"] == 0
        assert stats["total_conflicts"] == 0
        assert stats["domain_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_impact("p1", domain=PolicyDomain.SECURITY)
        eng.record_impact("p2", domain=PolicyDomain.FINANCIAL)
        eng.record_conflict("p1", "p2")
        stats = eng.get_stats()
        assert stats["total_impacts"] == 2
        assert stats["total_conflicts"] == 1
        assert stats["unique_policies"] == 2
