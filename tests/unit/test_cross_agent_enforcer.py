"""Tests for shieldops.policy.cross_agent_enforcer — CrossAgentPolicyEnforcer."""

from __future__ import annotations

from shieldops.policy.cross_agent_enforcer import (
    CrossAgentPolicyEnforcer,
    EnforcementAction,
    EnforcementRecord,
    PolicyEnforcerReport,
    PolicyRule,
    PolicyScope,
    ViolationType,
)


def _engine(**kw) -> CrossAgentPolicyEnforcer:
    return CrossAgentPolicyEnforcer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # PolicyScope (5)
    def test_scope_single_agent(self):
        assert PolicyScope.SINGLE_AGENT == "single_agent"

    def test_scope_team(self):
        assert PolicyScope.TEAM == "team"

    def test_scope_swarm(self):
        assert PolicyScope.SWARM == "swarm"

    def test_scope_global(self):
        assert PolicyScope.GLOBAL == "global"

    def test_scope_environment(self):
        assert PolicyScope.ENVIRONMENT == "environment"

    # EnforcementAction (5)
    def test_action_allow(self):
        assert EnforcementAction.ALLOW == "allow"

    def test_action_deny(self):
        assert EnforcementAction.DENY == "deny"

    def test_action_require_approval(self):
        assert EnforcementAction.REQUIRE_APPROVAL == "require_approval"

    def test_action_rate_limit(self):
        assert EnforcementAction.RATE_LIMIT == "rate_limit"

    def test_action_quarantine(self):
        assert EnforcementAction.QUARANTINE == "quarantine"

    # ViolationType (5)
    def test_violation_resource_conflict(self):
        assert ViolationType.RESOURCE_CONFLICT == "resource_conflict"

    def test_violation_scope_exceeded(self):
        assert ViolationType.SCOPE_EXCEEDED == "scope_exceeded"

    def test_violation_rate_exceeded(self):
        assert ViolationType.RATE_EXCEEDED == "rate_exceeded"

    def test_violation_unauthorized_action(self):
        assert ViolationType.UNAUTHORIZED_ACTION == "unauthorized_action"

    def test_violation_policy_bypass(self):
        assert ViolationType.POLICY_BYPASS == "policy_bypass"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_enforcement_record_defaults(self):
        r = EnforcementRecord()
        assert r.id
        assert r.agent_name == ""
        assert r.policy_scope == PolicyScope.SINGLE_AGENT
        assert r.enforcement_action == EnforcementAction.ALLOW
        assert r.violation_type == ViolationType.RESOURCE_CONFLICT
        assert r.severity_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_policy_rule_defaults(self):
        r = PolicyRule()
        assert r.id
        assert r.rule_name == ""
        assert r.policy_scope == PolicyScope.GLOBAL
        assert r.enforcement_action == EnforcementAction.DENY
        assert r.max_violations == 0
        assert r.created_at > 0

    def test_report_defaults(self):
        r = PolicyEnforcerReport()
        assert r.total_enforcements == 0
        assert r.total_rules == 0
        assert r.compliance_rate_pct == 0.0
        assert r.by_scope == {}
        assert r.by_action == {}
        assert r.violation_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_enforcement
# -------------------------------------------------------------------


class TestRecordEnforcement:
    def test_basic(self):
        eng = _engine()
        r = eng.record_enforcement(
            "agent-a",
            policy_scope=PolicyScope.TEAM,
            enforcement_action=EnforcementAction.DENY,
        )
        assert r.agent_name == "agent-a"
        assert r.policy_scope == PolicyScope.TEAM

    def test_with_severity(self):
        eng = _engine()
        r = eng.record_enforcement("agent-b", severity_score=8.5)
        assert r.severity_score == 8.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_enforcement(f"agent-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_enforcement
# -------------------------------------------------------------------


class TestGetEnforcement:
    def test_found(self):
        eng = _engine()
        r = eng.record_enforcement("agent-a")
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
        eng.record_enforcement("agent-a")
        eng.record_enforcement("agent-b")
        assert len(eng.list_enforcements()) == 2

    def test_filter_by_agent(self):
        eng = _engine()
        eng.record_enforcement("agent-a")
        eng.record_enforcement("agent-b")
        results = eng.list_enforcements(agent_name="agent-a")
        assert len(results) == 1

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_enforcement("agent-a", policy_scope=PolicyScope.GLOBAL)
        eng.record_enforcement("agent-b", policy_scope=PolicyScope.SINGLE_AGENT)
        results = eng.list_enforcements(policy_scope=PolicyScope.GLOBAL)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        r = eng.add_rule(
            "rule-1",
            policy_scope=PolicyScope.SWARM,
            enforcement_action=EnforcementAction.QUARANTINE,
            max_violations=5,
        )
        assert r.rule_name == "rule-1"
        assert r.max_violations == 5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._rules) == 2


# -------------------------------------------------------------------
# analyze_agent_compliance
# -------------------------------------------------------------------


class TestAnalyzeAgentCompliance:
    def test_with_data(self):
        eng = _engine()
        eng.record_enforcement("agent-a", enforcement_action=EnforcementAction.DENY)
        eng.record_enforcement("agent-a", enforcement_action=EnforcementAction.ALLOW)
        result = eng.analyze_agent_compliance("agent-a")
        assert result["agent_name"] == "agent-a"
        assert result["total_records"] == 2
        assert result["violation_count"] == 1
        assert result["compliance_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_agent_compliance("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(max_violations_per_agent=10)
        eng.record_enforcement("agent-a", enforcement_action=EnforcementAction.ALLOW)
        result = eng.analyze_agent_compliance("agent-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_repeat_violators
# -------------------------------------------------------------------


class TestIdentifyRepeatViolators:
    def test_with_violators(self):
        eng = _engine()
        eng.record_enforcement("agent-a", enforcement_action=EnforcementAction.DENY)
        eng.record_enforcement("agent-a", enforcement_action=EnforcementAction.QUARANTINE)
        eng.record_enforcement("agent-b", enforcement_action=EnforcementAction.ALLOW)
        results = eng.identify_repeat_violators()
        assert len(results) == 1
        assert results[0]["agent_name"] == "agent-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_repeat_violators() == []


# -------------------------------------------------------------------
# rank_by_violation_count
# -------------------------------------------------------------------


class TestRankByViolationCount:
    def test_with_data(self):
        eng = _engine()
        eng.record_enforcement("agent-a", severity_score=9.0)
        eng.record_enforcement("agent-a", severity_score=7.0)
        eng.record_enforcement("agent-b", severity_score=3.0)
        results = eng.rank_by_violation_count()
        assert results[0]["agent_name"] == "agent-a"
        assert results[0]["avg_severity_score"] == 8.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_violation_count() == []


# -------------------------------------------------------------------
# detect_policy_bypass_attempts
# -------------------------------------------------------------------


class TestDetectPolicyBypassAttempts:
    def test_with_recurring(self):
        eng = _engine()
        for _ in range(5):
            eng.record_enforcement("agent-a", violation_type=ViolationType.POLICY_BYPASS)
        eng.record_enforcement("agent-b", violation_type=ViolationType.POLICY_BYPASS)
        results = eng.detect_policy_bypass_attempts()
        assert len(results) == 1
        assert results[0]["agent_name"] == "agent-a"
        assert results[0]["recurring"] is True

    def test_no_recurring(self):
        eng = _engine()
        eng.record_enforcement("agent-a", violation_type=ViolationType.POLICY_BYPASS)
        assert eng.detect_policy_bypass_attempts() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_enforcement("agent-a", enforcement_action=EnforcementAction.DENY)
        eng.record_enforcement("agent-b", enforcement_action=EnforcementAction.ALLOW)
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_enforcements == 2
        assert report.total_rules == 1
        assert report.by_scope != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_enforcements == 0
        assert report.recommendations[0] == "Cross-agent policy compliance meets targets"

    def test_violation_recommendation(self):
        eng = _engine()
        eng.record_enforcement("agent-a", enforcement_action=EnforcementAction.DENY)
        report = eng.generate_report()
        assert "violation" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_enforcement("agent-a")
        eng.add_rule("rule-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["scope_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_enforcement("agent-a", policy_scope=PolicyScope.GLOBAL)
        eng.record_enforcement("agent-b", policy_scope=PolicyScope.TEAM)
        eng.add_rule("rule-1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_agents"] == 2
