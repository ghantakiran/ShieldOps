"""Tests for shieldops.compliance.policy_enforcer — PolicyEnforcementMonitor."""

from __future__ import annotations

from shieldops.compliance.policy_enforcer import (
    EnforcementAction,
    EnforcementRecord,
    EnforcementScope,
    EnforcementViolation,
    PolicyCategory,
    PolicyEnforcementMonitor,
    PolicyEnforcerReport,
)


def _engine(**kw) -> PolicyEnforcementMonitor:
    return PolicyEnforcementMonitor(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # EnforcementAction (5)
    def test_action_block(self):
        assert EnforcementAction.BLOCK == "block"

    def test_action_warn(self):
        assert EnforcementAction.WARN == "warn"

    def test_action_audit(self):
        assert EnforcementAction.AUDIT == "audit"

    def test_action_remediate(self):
        assert EnforcementAction.REMEDIATE == "remediate"

    def test_action_exempt(self):
        assert EnforcementAction.EXEMPT == "exempt"

    # EnforcementScope (5)
    def test_scope_organization(self):
        assert EnforcementScope.ORGANIZATION == "organization"

    def test_scope_team(self):
        assert EnforcementScope.TEAM == "team"

    def test_scope_service(self):
        assert EnforcementScope.SERVICE == "service"

    def test_scope_environment(self):
        assert EnforcementScope.ENVIRONMENT == "environment"

    def test_scope_resource(self):
        assert EnforcementScope.RESOURCE == "resource"

    # PolicyCategory (5)
    def test_category_security(self):
        assert PolicyCategory.SECURITY == "security"

    def test_category_compliance(self):
        assert PolicyCategory.COMPLIANCE == "compliance"

    def test_category_cost(self):
        assert PolicyCategory.COST == "cost"

    def test_category_operational(self):
        assert PolicyCategory.OPERATIONAL == "operational"

    def test_category_governance(self):
        assert PolicyCategory.GOVERNANCE == "governance"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_enforcement_record_defaults(self):
        r = EnforcementRecord()
        assert r.id
        assert r.policy_name == ""
        assert r.action == EnforcementAction.AUDIT
        assert r.scope == EnforcementScope.SERVICE
        assert r.category == PolicyCategory.SECURITY
        assert r.target == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_enforcement_violation_defaults(self):
        r = EnforcementViolation()
        assert r.id
        assert r.policy_name == ""
        assert r.scope == EnforcementScope.SERVICE
        assert r.category == PolicyCategory.SECURITY
        assert r.target == ""
        assert r.violation_count == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_policy_enforcer_report_defaults(self):
        r = PolicyEnforcerReport()
        assert r.total_enforcements == 0
        assert r.total_violations == 0
        assert r.violation_rate_pct == 0.0
        assert r.by_action == {}
        assert r.by_category == {}
        assert r.frequent_violation_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_enforcement
# -------------------------------------------------------------------


class TestRecordEnforcement:
    def test_basic(self):
        eng = _engine()
        r = eng.record_enforcement(
            "policy-a",
            action=EnforcementAction.BLOCK,
            scope=EnforcementScope.SERVICE,
        )
        assert r.policy_name == "policy-a"
        assert r.action == EnforcementAction.BLOCK

    def test_with_category(self):
        eng = _engine()
        r = eng.record_enforcement(
            "policy-b",
            category=PolicyCategory.COST,
        )
        assert r.category == PolicyCategory.COST

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_enforcement(f"policy-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_enforcement
# -------------------------------------------------------------------


class TestGetEnforcement:
    def test_found(self):
        eng = _engine()
        r = eng.record_enforcement("policy-a")
        assert eng.get_enforcement(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_enforcement("nonexistent") is None


# -------------------------------------------------------------------
# list_enforcements
# -------------------------------------------------------------------


class TestListEnforcements:
    def test_list_all(self):
        eng = _engine()
        eng.record_enforcement("policy-a")
        eng.record_enforcement("policy-b")
        assert len(eng.list_enforcements()) == 2

    def test_filter_by_policy_name(self):
        eng = _engine()
        eng.record_enforcement("policy-a")
        eng.record_enforcement("policy-b")
        results = eng.list_enforcements(policy_name="policy-a")
        assert len(results) == 1

    def test_filter_by_action(self):
        eng = _engine()
        eng.record_enforcement("policy-a", action=EnforcementAction.BLOCK)
        eng.record_enforcement("policy-b", action=EnforcementAction.WARN)
        results = eng.list_enforcements(action=EnforcementAction.BLOCK)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_violation
# -------------------------------------------------------------------


class TestAddViolation:
    def test_basic(self):
        eng = _engine()
        v = eng.add_violation(
            "policy-a",
            scope=EnforcementScope.ORGANIZATION,
            category=PolicyCategory.SECURITY,
            target="svc-a",
            violation_count=3,
        )
        assert v.policy_name == "policy-a"
        assert v.violation_count == 3

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_violation(f"policy-{i}")
        assert len(eng._violations) == 2


# -------------------------------------------------------------------
# analyze_enforcement_by_policy
# -------------------------------------------------------------------


class TestAnalyzeEnforcementByPolicy:
    def test_with_data(self):
        eng = _engine()
        eng.record_enforcement("policy-a", action=EnforcementAction.BLOCK)
        eng.record_enforcement("policy-a", action=EnforcementAction.WARN)
        result = eng.analyze_enforcement_by_policy("policy-a")
        assert result["policy_name"] == "policy-a"
        assert result["total_enforcements"] == 2
        assert result["block_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_enforcement_by_policy("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_frequent_violations
# -------------------------------------------------------------------


class TestIdentifyFrequentViolations:
    def test_with_violations(self):
        eng = _engine()
        eng.add_violation("policy-a")
        eng.add_violation("policy-a")
        eng.add_violation("policy-b")
        results = eng.identify_frequent_violations()
        assert len(results) == 1
        assert results[0]["policy_name"] == "policy-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_frequent_violations() == []


# -------------------------------------------------------------------
# rank_by_violation_count
# -------------------------------------------------------------------


class TestRankByViolationCount:
    def test_with_data(self):
        eng = _engine()
        eng.record_enforcement("policy-a")
        eng.record_enforcement("policy-a")
        eng.record_enforcement("policy-b")
        results = eng.rank_by_violation_count()
        assert results[0]["policy_name"] == "policy-a"
        assert results[0]["enforcement_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_violation_count() == []


# -------------------------------------------------------------------
# detect_enforcement_trends
# -------------------------------------------------------------------


class TestDetectEnforcementTrends:
    def test_with_trends(self):
        eng = _engine()
        for _ in range(5):
            eng.record_enforcement("policy-a", action=EnforcementAction.BLOCK)
        eng.record_enforcement("policy-b", action=EnforcementAction.WARN)
        results = eng.detect_enforcement_trends()
        assert len(results) == 1
        assert results[0]["policy_name"] == "policy-a"
        assert results[0]["trend_detected"] is True

    def test_no_trends(self):
        eng = _engine()
        eng.record_enforcement("policy-a", action=EnforcementAction.BLOCK)
        assert eng.detect_enforcement_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_enforcement("policy-a", action=EnforcementAction.BLOCK)
        eng.record_enforcement("policy-b", action=EnforcementAction.WARN)
        eng.add_violation("policy-a")
        report = eng.generate_report()
        assert report.total_enforcements == 2
        assert report.total_violations == 1
        assert report.by_action != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_enforcements == 0
        assert "acceptable" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_enforcement("policy-a")
        eng.add_violation("policy-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._violations) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_enforcements"] == 0
        assert stats["total_violations"] == 0
        assert stats["action_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_enforcement("policy-a", action=EnforcementAction.BLOCK)
        eng.record_enforcement("policy-b", action=EnforcementAction.WARN)
        eng.add_violation("policy-a")
        stats = eng.get_stats()
        assert stats["total_enforcements"] == 2
        assert stats["total_violations"] == 1
        assert stats["unique_policies"] == 2
