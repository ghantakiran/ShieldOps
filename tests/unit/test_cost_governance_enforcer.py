"""Tests for shieldops.billing.cost_governance_enforcer — CostGovernanceEnforcer."""

from __future__ import annotations

from shieldops.billing.cost_governance_enforcer import (
    CostGovernanceEnforcer,
    CostGovernanceReport,
    EnforcementAction,
    GovernanceRecord,
    GovernanceViolation,
    PolicyScope,
    ViolationType,
)


def _engine(**kw) -> CostGovernanceEnforcer:
    return CostGovernanceEnforcer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_budget_exceeded(self):
        assert ViolationType.BUDGET_EXCEEDED == "budget_exceeded"

    def test_type_unapproved_resource(self):
        assert ViolationType.UNAPPROVED_RESOURCE == "unapproved_resource"

    def test_type_missing_approval(self):
        assert ViolationType.MISSING_APPROVAL == "missing_approval"

    def test_type_tag_noncompliant(self):
        assert ViolationType.TAG_NONCOMPLIANT == "tag_noncompliant"

    def test_type_rate_exceeded(self):
        assert ViolationType.RATE_EXCEEDED == "rate_exceeded"

    def test_action_alert(self):
        assert EnforcementAction.ALERT == "alert"

    def test_action_block(self):
        assert EnforcementAction.BLOCK == "block"

    def test_action_quarantine(self):
        assert EnforcementAction.QUARANTINE == "quarantine"

    def test_action_require_approval(self):
        assert EnforcementAction.REQUIRE_APPROVAL == "require_approval"

    def test_action_auto_remediate(self):
        assert EnforcementAction.AUTO_REMEDIATE == "auto_remediate"

    def test_scope_organization(self):
        assert PolicyScope.ORGANIZATION == "organization"

    def test_scope_department(self):
        assert PolicyScope.DEPARTMENT == "department"

    def test_scope_team(self):
        assert PolicyScope.TEAM == "team"

    def test_scope_project(self):
        assert PolicyScope.PROJECT == "project"

    def test_scope_individual(self):
        assert PolicyScope.INDIVIDUAL == "individual"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_governance_record_defaults(self):
        r = GovernanceRecord()
        assert r.id
        assert r.policy_name == ""
        assert r.violation_type == ViolationType.BUDGET_EXCEEDED
        assert r.enforcement_action == EnforcementAction.ALERT
        assert r.policy_scope == PolicyScope.ORGANIZATION
        assert r.violation_count == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_governance_violation_defaults(self):
        v = GovernanceViolation()
        assert v.id
        assert v.policy_name == ""
        assert v.violation_type == ViolationType.BUDGET_EXCEEDED
        assert v.violation_score == 0.0
        assert v.threshold == 0.0
        assert v.breached is False
        assert v.description == ""
        assert v.created_at > 0

    def test_cost_governance_report_defaults(self):
        r = CostGovernanceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_violations == 0
        assert r.high_violation_count == 0
        assert r.avg_violation_count == 0.0
        assert r.by_type == {}
        assert r.by_action == {}
        assert r.by_scope == {}
        assert r.top_violators == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_governance
# ---------------------------------------------------------------------------


class TestRecordGovernance:
    def test_basic(self):
        eng = _engine()
        r = eng.record_governance(
            policy_name="budget-limit-prod",
            violation_type=ViolationType.UNAPPROVED_RESOURCE,
            enforcement_action=EnforcementAction.BLOCK,
            policy_scope=PolicyScope.DEPARTMENT,
            violation_count=15.0,
            service="api-gateway",
            team="sre",
        )
        assert r.policy_name == "budget-limit-prod"
        assert r.violation_type == ViolationType.UNAPPROVED_RESOURCE
        assert r.enforcement_action == EnforcementAction.BLOCK
        assert r.policy_scope == PolicyScope.DEPARTMENT
        assert r.violation_count == 15.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_governance(policy_name=f"policy-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_governance
# ---------------------------------------------------------------------------


class TestGetGovernance:
    def test_found(self):
        eng = _engine()
        r = eng.record_governance(
            policy_name="budget-limit-prod",
            violation_type=ViolationType.TAG_NONCOMPLIANT,
        )
        result = eng.get_governance(r.id)
        assert result is not None
        assert result.violation_type == ViolationType.TAG_NONCOMPLIANT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_governance("nonexistent") is None


# ---------------------------------------------------------------------------
# list_governance_records
# ---------------------------------------------------------------------------


class TestListGovernanceRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_governance(policy_name="policy-1")
        eng.record_governance(policy_name="policy-2")
        assert len(eng.list_governance_records()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_governance(
            policy_name="policy-1",
            violation_type=ViolationType.BUDGET_EXCEEDED,
        )
        eng.record_governance(
            policy_name="policy-2",
            violation_type=ViolationType.TAG_NONCOMPLIANT,
        )
        results = eng.list_governance_records(
            violation_type=ViolationType.BUDGET_EXCEEDED,
        )
        assert len(results) == 1

    def test_filter_by_action(self):
        eng = _engine()
        eng.record_governance(
            policy_name="policy-1",
            enforcement_action=EnforcementAction.BLOCK,
        )
        eng.record_governance(
            policy_name="policy-2",
            enforcement_action=EnforcementAction.QUARANTINE,
        )
        results = eng.list_governance_records(
            enforcement_action=EnforcementAction.BLOCK,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_governance(policy_name="policy-1", team="sre")
        eng.record_governance(policy_name="policy-2", team="platform")
        results = eng.list_governance_records(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_governance(policy_name=f"policy-{i}")
        assert len(eng.list_governance_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_violation
# ---------------------------------------------------------------------------


class TestAddViolation:
    def test_basic(self):
        eng = _engine()
        v = eng.add_violation(
            policy_name="budget-limit-prod",
            violation_type=ViolationType.RATE_EXCEEDED,
            violation_score=85.0,
            threshold=10.0,
            breached=True,
            description="Rate limit exceeded",
        )
        assert v.policy_name == "budget-limit-prod"
        assert v.violation_type == ViolationType.RATE_EXCEEDED
        assert v.violation_score == 85.0
        assert v.threshold == 10.0
        assert v.breached is True
        assert v.description == "Rate limit exceeded"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_violation(policy_name=f"policy-{i}")
        assert len(eng._violations) == 2


# ---------------------------------------------------------------------------
# analyze_violation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeViolationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_governance(
            policy_name="policy-1",
            violation_type=ViolationType.BUDGET_EXCEEDED,
            violation_count=5.0,
        )
        eng.record_governance(
            policy_name="policy-2",
            violation_type=ViolationType.BUDGET_EXCEEDED,
            violation_count=15.0,
        )
        result = eng.analyze_violation_distribution()
        assert "budget_exceeded" in result
        assert result["budget_exceeded"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_violation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_violation_policies
# ---------------------------------------------------------------------------


class TestIdentifyHighViolationPolicies:
    def test_detects(self):
        eng = _engine(max_violation_rate=10.0)
        eng.record_governance(
            policy_name="policy-high",
            violation_count=25.0,
        )
        eng.record_governance(
            policy_name="policy-low",
            violation_count=3.0,
        )
        results = eng.identify_high_violation_policies()
        assert len(results) == 1
        assert results[0]["policy_name"] == "policy-high"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_violation_policies() == []


# ---------------------------------------------------------------------------
# rank_by_violation_rate
# ---------------------------------------------------------------------------


class TestRankByViolationRate:
    def test_ranked(self):
        eng = _engine()
        eng.record_governance(
            policy_name="policy-1",
            service="api-gateway",
            violation_count=5.0,
        )
        eng.record_governance(
            policy_name="policy-2",
            service="payments",
            violation_count=25.0,
        )
        results = eng.rank_by_violation_rate()
        assert len(results) == 2
        assert results[0]["service"] == "payments"
        assert results[0]["avg_violation_count"] == 25.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_violation_rate() == []


# ---------------------------------------------------------------------------
# detect_governance_trends
# ---------------------------------------------------------------------------


class TestDetectGovernanceTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_violation(
                policy_name="policy-1",
                violation_score=50.0,
            )
        result = eng.detect_governance_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_violation(policy_name="policy-1", violation_score=30.0)
        eng.add_violation(policy_name="policy-2", violation_score=30.0)
        eng.add_violation(policy_name="policy-3", violation_score=80.0)
        eng.add_violation(policy_name="policy-4", violation_score=80.0)
        result = eng.detect_governance_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_governance_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_violation_rate=10.0)
        eng.record_governance(
            policy_name="budget-limit-prod",
            violation_type=ViolationType.BUDGET_EXCEEDED,
            enforcement_action=EnforcementAction.BLOCK,
            policy_scope=PolicyScope.DEPARTMENT,
            violation_count=25.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CostGovernanceReport)
        assert report.total_records == 1
        assert report.high_violation_count == 1
        assert len(report.top_violators) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_governance(policy_name="policy-1")
        eng.add_violation(policy_name="policy-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._violations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_violations"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_governance(
            policy_name="budget-limit-prod",
            violation_type=ViolationType.BUDGET_EXCEEDED,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "budget_exceeded" in stats["type_distribution"]
