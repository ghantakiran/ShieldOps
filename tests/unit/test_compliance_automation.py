"""Tests for shieldops.compliance.automation_rules — ComplianceAutomationEngine.

Covers:
- RuleAction, RuleStatus, ExecutionResult enums
- ComplianceRule, ViolationEvent, RuleExecution model defaults
- create_rule (basic, unique IDs, extra fields, eviction at max)
- update_rule (basic, not found)
- delete_rule (success, not found)
- report_violation (basic)
- evaluate_violation (basic, no matching rules, not found)
- list_rules (all, filter by status, filter by action)
- list_executions (all, filter by rule, filter by result)
- list_violations (all, filter by type, filter by severity)
- get_effectiveness (basic, empty)
- get_stats (empty, populated)
"""

from __future__ import annotations

from shieldops.compliance.automation_rules import (
    ComplianceAutomationEngine,
    ComplianceRule,
    ExecutionResult,
    RuleAction,
    RuleExecution,
    RuleStatus,
    ViolationEvent,
)


def _engine(**kw) -> ComplianceAutomationEngine:
    return ComplianceAutomationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # RuleAction (5 values)

    def test_action_notify(self):
        assert RuleAction.NOTIFY == "notify"

    def test_action_auto_remediate(self):
        assert RuleAction.AUTO_REMEDIATE == "auto_remediate"

    def test_action_quarantine(self):
        assert RuleAction.QUARANTINE == "quarantine"

    def test_action_escalate(self):
        assert RuleAction.ESCALATE == "escalate"

    def test_action_log_only(self):
        assert RuleAction.LOG_ONLY == "log_only"

    # RuleStatus (3 values)

    def test_status_active(self):
        assert RuleStatus.ACTIVE == "active"

    def test_status_disabled(self):
        assert RuleStatus.DISABLED == "disabled"

    def test_status_testing(self):
        assert RuleStatus.TESTING == "testing"

    # ExecutionResult (4 values)

    def test_result_success(self):
        assert ExecutionResult.SUCCESS == "success"

    def test_result_failure(self):
        assert ExecutionResult.FAILURE == "failure"

    def test_result_skipped(self):
        assert ExecutionResult.SKIPPED == "skipped"

    def test_result_dry_run(self):
        assert ExecutionResult.DRY_RUN == "dry_run"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_compliance_rule_defaults(self):
        rule = ComplianceRule(name="encryption-check")
        assert rule.id
        assert rule.name == "encryption-check"
        assert rule.description == ""
        assert rule.framework == ""
        assert rule.condition == ""
        assert rule.action == RuleAction.NOTIFY
        assert rule.status == RuleStatus.ACTIVE
        assert rule.severity == "medium"
        assert rule.tags == []
        assert rule.created_at > 0
        assert rule.updated_at > 0

    def test_violation_event_defaults(self):
        v = ViolationEvent(resource_id="res-001")
        assert v.id
        assert v.resource_id == "res-001"
        assert v.resource_type == ""
        assert v.rule_id == ""
        assert v.description == ""
        assert v.severity == "medium"
        assert v.detected_at > 0

    def test_rule_execution_defaults(self):
        ex = RuleExecution(
            rule_id="r1",
            violation_id="v1",
            action=RuleAction.NOTIFY,
            result=ExecutionResult.SUCCESS,
        )
        assert ex.id
        assert ex.rule_id == "r1"
        assert ex.violation_id == "v1"
        assert ex.action == RuleAction.NOTIFY
        assert ex.result == ExecutionResult.SUCCESS
        assert ex.details == ""
        assert ex.executed_at > 0


# ---------------------------------------------------------------------------
# create_rule
# ---------------------------------------------------------------------------


class TestCreateRule:
    def test_basic(self):
        e = _engine()
        rule = e.create_rule("encryption-check", action=RuleAction.AUTO_REMEDIATE)
        assert rule.name == "encryption-check"
        assert rule.action == RuleAction.AUTO_REMEDIATE
        assert rule.status == RuleStatus.ACTIVE

    def test_unique_ids(self):
        e = _engine()
        r1 = e.create_rule("rule-a")
        r2 = e.create_rule("rule-b")
        assert r1.id != r2.id

    def test_extra_fields(self):
        e = _engine()
        rule = e.create_rule(
            "pci-check",
            action=RuleAction.QUARANTINE,
            framework="PCI-DSS",
            severity="critical",
            description="Ensure PCI compliance",
            tags=["pci", "network"],
        )
        assert rule.framework == "PCI-DSS"
        assert rule.severity == "critical"
        assert rule.description == "Ensure PCI compliance"
        assert rule.tags == ["pci", "network"]

    def test_evicts_at_max(self):
        e = _engine(max_rules=2)
        r1 = e.create_rule("rule-a")
        e.create_rule("rule-b")
        e.create_rule("rule-c")
        rules = e.list_rules()
        ids = {r.id for r in rules}
        assert r1.id not in ids
        assert len(rules) == 2


# ---------------------------------------------------------------------------
# update_rule
# ---------------------------------------------------------------------------


class TestUpdateRule:
    def test_basic(self):
        e = _engine()
        rule = e.create_rule("original")
        updated = e.update_rule(rule.id, name="updated", severity="high")
        assert updated is not None
        assert updated.name == "updated"
        assert updated.severity == "high"

    def test_not_found(self):
        e = _engine()
        assert e.update_rule("nonexistent", name="x") is None


# ---------------------------------------------------------------------------
# delete_rule
# ---------------------------------------------------------------------------


class TestDeleteRule:
    def test_success(self):
        e = _engine()
        rule = e.create_rule("to-delete")
        assert e.delete_rule(rule.id) is True
        assert e.list_rules() == []

    def test_not_found(self):
        e = _engine()
        assert e.delete_rule("nonexistent") is False


# ---------------------------------------------------------------------------
# report_violation
# ---------------------------------------------------------------------------


class TestReportViolation:
    def test_basic(self):
        e = _engine()
        v = e.report_violation(
            resource_id="s3-bucket-001",
            resource_type="s3_bucket",
            description="Bucket is public",
            severity="high",
        )
        assert v.resource_id == "s3-bucket-001"
        assert v.resource_type == "s3_bucket"
        assert v.description == "Bucket is public"
        assert v.severity == "high"


# ---------------------------------------------------------------------------
# evaluate_violation
# ---------------------------------------------------------------------------


class TestEvaluateViolation:
    def test_basic(self):
        e = _engine()
        rule = e.create_rule("public-bucket", action=RuleAction.QUARANTINE)
        v = e.report_violation(resource_id="bucket-1")
        executions = e.evaluate_violation(v.id)
        assert len(executions) == 1
        assert executions[0].rule_id == rule.id
        assert executions[0].violation_id == v.id
        assert executions[0].action == RuleAction.QUARANTINE
        assert executions[0].result == ExecutionResult.SUCCESS

    def test_no_matching_rules_disabled(self):
        e = _engine()
        rule = e.create_rule("disabled-rule", action=RuleAction.NOTIFY)
        e.update_rule(rule.id, status=RuleStatus.DISABLED)
        v = e.report_violation(resource_id="bucket-1")
        executions = e.evaluate_violation(v.id)
        assert len(executions) == 0

    def test_violation_not_found(self):
        e = _engine()
        e.create_rule("some-rule")
        executions = e.evaluate_violation("nonexistent")
        assert executions == []


# ---------------------------------------------------------------------------
# list_rules
# ---------------------------------------------------------------------------


class TestListRules:
    def test_list_all(self):
        e = _engine()
        e.create_rule("rule-a")
        e.create_rule("rule-b")
        e.create_rule("rule-c")
        assert len(e.list_rules()) == 3

    def test_filter_by_status(self):
        e = _engine()
        e.create_rule("active-rule", status=RuleStatus.ACTIVE)
        e.create_rule("disabled-rule", status=RuleStatus.DISABLED)
        active = e.list_rules(status=RuleStatus.ACTIVE)
        assert len(active) == 1
        assert active[0].name == "active-rule"

    def test_filter_by_action(self):
        e = _engine()
        e.create_rule("notify-rule", action=RuleAction.NOTIFY)
        e.create_rule("quarantine-rule", action=RuleAction.QUARANTINE)
        quarantine = e.list_rules(action=RuleAction.QUARANTINE)
        assert len(quarantine) == 1
        assert quarantine[0].name == "quarantine-rule"


# ---------------------------------------------------------------------------
# list_executions
# ---------------------------------------------------------------------------


class TestListExecutions:
    def test_list_all(self):
        e = _engine()
        e.create_rule("rule-a", action=RuleAction.NOTIFY)
        e.create_rule("rule-b", action=RuleAction.QUARANTINE)
        v = e.report_violation(resource_id="res-1")
        e.evaluate_violation(v.id)
        executions = e.list_executions()
        assert len(executions) == 2

    def test_filter_by_rule(self):
        e = _engine()
        r1 = e.create_rule("rule-a")
        e.create_rule("rule-b")
        v = e.report_violation(resource_id="res-1")
        e.evaluate_violation(v.id)
        filtered = e.list_executions(rule_id=r1.id)
        assert len(filtered) == 1
        assert filtered[0].rule_id == r1.id

    def test_filter_by_result(self):
        e = _engine()
        e.create_rule("rule-a")
        v = e.report_violation(resource_id="res-1")
        e.evaluate_violation(v.id)
        success = e.list_executions(result=ExecutionResult.SUCCESS)
        assert len(success) == 1
        skipped = e.list_executions(result=ExecutionResult.SKIPPED)
        assert len(skipped) == 0


# ---------------------------------------------------------------------------
# list_violations
# ---------------------------------------------------------------------------


class TestListViolations:
    def test_list_all(self):
        e = _engine()
        e.report_violation(resource_id="r1")
        e.report_violation(resource_id="r2")
        e.report_violation(resource_id="r3")
        assert len(e.list_violations()) == 3

    def test_filter_by_type(self):
        e = _engine()
        e.report_violation(resource_id="r1", resource_type="s3_bucket")
        e.report_violation(resource_id="r2", resource_type="ec2_instance")
        e.report_violation(resource_id="r3", resource_type="s3_bucket")
        filtered = e.list_violations(resource_type="s3_bucket")
        assert len(filtered) == 2
        assert all(v.resource_type == "s3_bucket" for v in filtered)

    def test_filter_by_severity(self):
        e = _engine()
        e.report_violation(resource_id="r1", severity="high")
        e.report_violation(resource_id="r2", severity="low")
        e.report_violation(resource_id="r3", severity="high")
        filtered = e.list_violations(severity="high")
        assert len(filtered) == 2
        assert all(v.severity == "high" for v in filtered)


# ---------------------------------------------------------------------------
# get_effectiveness
# ---------------------------------------------------------------------------


class TestGetEffectiveness:
    def test_basic(self):
        e = _engine()
        rule = e.create_rule("check-rule", action=RuleAction.NOTIFY)
        v1 = e.report_violation(resource_id="r1")
        v2 = e.report_violation(resource_id="r2")
        e.evaluate_violation(v1.id)
        e.evaluate_violation(v2.id)
        eff = e.get_effectiveness()
        assert eff["total_rules_evaluated"] == 1
        assert len(eff["rules"]) == 1
        assert eff["rules"][0]["rule_id"] == rule.id
        assert eff["rules"][0]["total_executions"] == 2
        assert eff["rules"][0]["successful"] == 2
        assert eff["rules"][0]["success_rate"] == 1.0

    def test_empty(self):
        e = _engine()
        eff = e.get_effectiveness()
        assert eff["total_rules_evaluated"] == 0
        assert eff["rules"] == []


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        e = _engine()
        stats = e.get_stats()
        assert stats["total_rules"] == 0
        assert stats["total_violations"] == 0
        assert stats["total_executions"] == 0
        assert stats["rule_action_distribution"] == {}
        assert stats["rule_status_distribution"] == {}
        assert stats["execution_result_distribution"] == {}

    def test_populated(self):
        e = _engine()
        e.create_rule("rule-a", action=RuleAction.NOTIFY)
        e.create_rule("rule-b", action=RuleAction.QUARANTINE)
        v = e.report_violation(resource_id="r1")
        e.evaluate_violation(v.id)
        stats = e.get_stats()
        assert stats["total_rules"] == 2
        assert stats["total_violations"] == 1
        assert stats["total_executions"] == 2
        assert RuleAction.NOTIFY in stats["rule_action_distribution"]
        assert RuleAction.QUARANTINE in stats["rule_action_distribution"]
        assert RuleStatus.ACTIVE in stats["rule_status_distribution"]
        assert ExecutionResult.SUCCESS in stats["execution_result_distribution"]
