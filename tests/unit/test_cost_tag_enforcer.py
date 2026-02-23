"""Tests for shieldops.billing.cost_tag_enforcer — CostAllocationTagEnforcer."""

from __future__ import annotations

import pytest

from shieldops.billing.cost_tag_enforcer import (
    CostAllocationTagEnforcer,
    CostTagPolicy,
    EnforcementAction,
    EnforcementMode,
    ResourceStatus,
    ResourceTagCheck,
    TagRequirement,
)


def _enforcer(**kw) -> CostAllocationTagEnforcer:
    return CostAllocationTagEnforcer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # EnforcementMode (4 values)

    def test_enforcement_mode_audit(self):
        assert EnforcementMode.AUDIT == "audit"

    def test_enforcement_mode_warn(self):
        assert EnforcementMode.WARN == "warn"

    def test_enforcement_mode_block(self):
        assert EnforcementMode.BLOCK == "block"

    def test_enforcement_mode_auto_tag(self):
        assert EnforcementMode.AUTO_TAG == "auto_tag"

    # TagRequirement (3 values)

    def test_tag_requirement_required(self):
        assert TagRequirement.REQUIRED == "required"

    def test_tag_requirement_recommended(self):
        assert TagRequirement.RECOMMENDED == "recommended"

    def test_tag_requirement_optional(self):
        assert TagRequirement.OPTIONAL == "optional"

    # ResourceStatus (4 values)

    def test_resource_status_compliant(self):
        assert ResourceStatus.COMPLIANT == "compliant"

    def test_resource_status_non_compliant(self):
        assert ResourceStatus.NON_COMPLIANT == "non_compliant"

    def test_resource_status_remediated(self):
        assert ResourceStatus.REMEDIATED == "remediated"

    def test_resource_status_exempted(self):
        assert ResourceStatus.EXEMPTED == "exempted"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_cost_tag_policy_defaults(self):
        policy = CostTagPolicy(name="standard-tags")
        assert policy.id
        assert policy.name == "standard-tags"
        assert policy.required_tags == []
        assert policy.tag_requirements == {}
        assert policy.enforcement_mode == EnforcementMode.AUDIT
        assert policy.resource_types == []
        assert policy.default_values == {}
        assert policy.created_at > 0
        assert policy.updated_at > 0

    def test_resource_tag_check_defaults(self):
        check = ResourceTagCheck(resource_id="r-1")
        assert check.id
        assert check.resource_id == "r-1"
        assert check.resource_type == ""
        assert check.policy_id == ""
        assert check.existing_tags == {}
        assert check.missing_tags == []
        assert check.status == ResourceStatus.COMPLIANT
        assert check.checked_at > 0

    def test_enforcement_action_defaults(self):
        action = EnforcementAction(
            check_id="c-1",
            resource_id="r-1",
            action_taken=EnforcementMode.AUDIT,
        )
        assert action.id
        assert action.check_id == "c-1"
        assert action.resource_id == "r-1"
        assert action.action_taken == EnforcementMode.AUDIT
        assert action.tags_applied == {}
        assert action.success is True
        assert action.details == ""
        assert action.executed_at > 0


# ---------------------------------------------------------------------------
# create_policy
# ---------------------------------------------------------------------------


class TestCreatePolicy:
    def test_basic_create(self):
        enf = _enforcer()
        policy = enf.create_policy("standard-tags", required_tags=["team", "env"])
        assert policy.name == "standard-tags"
        assert policy.required_tags == ["team", "env"]
        assert policy.enforcement_mode == EnforcementMode.AUDIT
        assert len(enf.list_policies()) == 1

    def test_create_assigns_unique_ids(self):
        enf = _enforcer()
        p1 = enf.create_policy("policy-a")
        p2 = enf.create_policy("policy-b")
        assert p1.id != p2.id

    def test_create_with_extra_fields(self):
        enf = _enforcer()
        policy = enf.create_policy(
            "auto-tag-policy",
            required_tags=["team", "cost-center"],
            enforcement_mode=EnforcementMode.AUTO_TAG,
            resource_types=["ec2", "rds"],
            default_values={"team": "platform", "cost-center": "engineering"},
        )
        assert policy.enforcement_mode == EnforcementMode.AUTO_TAG
        assert policy.resource_types == ["ec2", "rds"]
        assert policy.default_values == {"team": "platform", "cost-center": "engineering"}

    def test_evicts_at_max_policies(self):
        enf = _enforcer(max_policies=3)
        ids = []
        for i in range(4):
            policy = enf.create_policy(f"policy-{i}")
            ids.append(policy.id)
        assert len(enf.list_policies()) == 3
        # First policy should have been evicted
        found_ids = {p.id for p in enf.list_policies()}
        assert ids[0] not in found_ids
        assert ids[3] in found_ids


# ---------------------------------------------------------------------------
# update_policy
# ---------------------------------------------------------------------------


class TestUpdatePolicy:
    def test_basic_update(self):
        enf = _enforcer()
        policy = enf.create_policy("original", required_tags=["team"])
        result = enf.update_policy(policy.id, name="updated", required_tags=["team", "env"])
        assert result is not None
        assert result.name == "updated"
        assert result.required_tags == ["team", "env"]

    def test_update_not_found(self):
        enf = _enforcer()
        result = enf.update_policy("nonexistent", name="nope")
        assert result is None


# ---------------------------------------------------------------------------
# delete_policy
# ---------------------------------------------------------------------------


class TestDeletePolicy:
    def test_delete_success(self):
        enf = _enforcer()
        policy = enf.create_policy("deletable")
        assert enf.delete_policy(policy.id) is True
        assert len(enf.list_policies()) == 0

    def test_delete_not_found(self):
        enf = _enforcer()
        assert enf.delete_policy("nonexistent") is False


# ---------------------------------------------------------------------------
# check_resource
# ---------------------------------------------------------------------------


class TestCheckResource:
    def test_compliant_resource(self):
        enf = _enforcer()
        enf.create_policy("standard", required_tags=["team", "env"])
        check = enf.check_resource(
            "r-1",
            resource_type="ec2",
            existing_tags={"team": "platform", "env": "prod"},
        )
        assert check.status == ResourceStatus.COMPLIANT
        assert check.missing_tags == []

    def test_non_compliant_resource(self):
        enf = _enforcer()
        enf.create_policy("standard", required_tags=["team", "env", "cost-center"])
        check = enf.check_resource(
            "r-2",
            resource_type="rds",
            existing_tags={"team": "platform"},
        )
        assert check.status == ResourceStatus.NON_COMPLIANT
        assert "env" in check.missing_tags
        assert "cost-center" in check.missing_tags

    def test_check_with_specific_policy_id(self):
        enf = _enforcer()
        p1 = enf.create_policy("strict", required_tags=["team", "env", "owner"])
        enf.create_policy("relaxed", required_tags=["team"])
        check = enf.check_resource(
            "r-3",
            existing_tags={"team": "infra"},
            policy_id=p1.id,
        )
        assert check.status == ResourceStatus.NON_COMPLIANT
        assert "env" in check.missing_tags
        assert "owner" in check.missing_tags


# ---------------------------------------------------------------------------
# enforce
# ---------------------------------------------------------------------------


class TestEnforce:
    def test_auto_tag_enforcement(self):
        enf = _enforcer()
        policy = enf.create_policy(
            "auto-policy",
            required_tags=["team", "env"],
            enforcement_mode=EnforcementMode.AUTO_TAG,
            default_values={"team": "default-team", "env": "dev"},
        )
        check = enf.check_resource("r-1", existing_tags={}, policy_id=policy.id)
        assert check.status == ResourceStatus.NON_COMPLIANT
        action = enf.enforce(check.id)
        assert action is not None
        assert action.success is True
        assert action.action_taken == EnforcementMode.AUTO_TAG
        assert action.tags_applied["team"] == "default-team"
        assert action.tags_applied["env"] == "dev"
        # Check should be remediated
        assert check.status == ResourceStatus.REMEDIATED

    def test_enforce_not_found(self):
        enf = _enforcer()
        result = enf.enforce("nonexistent-check")
        assert result is None


# ---------------------------------------------------------------------------
# list_policies
# ---------------------------------------------------------------------------


class TestListPolicies:
    def test_basic_list(self):
        enf = _enforcer()
        enf.create_policy("policy-a")
        enf.create_policy("policy-b")
        policies = enf.list_policies()
        assert len(policies) == 2


# ---------------------------------------------------------------------------
# list_checks
# ---------------------------------------------------------------------------


class TestListChecks:
    def test_list_all(self):
        enf = _enforcer()
        enf.create_policy("standard", required_tags=["team"])
        enf.check_resource("r-1", existing_tags={"team": "a"})
        enf.check_resource("r-2", existing_tags={})
        checks = enf.list_checks()
        assert len(checks) == 2

    def test_filter_by_status(self):
        enf = _enforcer()
        enf.create_policy("standard", required_tags=["team"])
        enf.check_resource("r-1", existing_tags={"team": "a"})
        enf.check_resource("r-2", existing_tags={})
        compliant = enf.list_checks(status=ResourceStatus.COMPLIANT)
        assert len(compliant) == 1
        non_compliant = enf.list_checks(status=ResourceStatus.NON_COMPLIANT)
        assert len(non_compliant) == 1

    def test_filter_by_resource_type(self):
        enf = _enforcer()
        enf.create_policy("standard", required_tags=["team"])
        enf.check_resource("r-1", resource_type="ec2", existing_tags={"team": "a"})
        enf.check_resource("r-2", resource_type="rds", existing_tags={"team": "b"})
        enf.check_resource("r-3", resource_type="ec2", existing_tags={})
        results = enf.list_checks(resource_type="ec2")
        assert len(results) == 2
        assert all(c.resource_type == "ec2" for c in results)


# ---------------------------------------------------------------------------
# list_actions
# ---------------------------------------------------------------------------


class TestListActions:
    def test_basic_list(self):
        enf = _enforcer()
        policy = enf.create_policy(
            "auto-policy",
            required_tags=["team"],
            enforcement_mode=EnforcementMode.AUTO_TAG,
        )
        check = enf.check_resource("r-1", existing_tags={}, policy_id=policy.id)
        enf.enforce(check.id)
        actions = enf.list_actions()
        assert len(actions) == 1
        assert actions[0].resource_id == "r-1"


# ---------------------------------------------------------------------------
# get_compliance_summary
# ---------------------------------------------------------------------------


class TestGetComplianceSummary:
    def test_basic_summary(self):
        enf = _enforcer()
        enf.create_policy("standard", required_tags=["team"])
        enf.check_resource("r-1", existing_tags={"team": "a"})
        enf.check_resource("r-2", existing_tags={})
        enf.check_resource("r-3", existing_tags={"team": "b"})
        summary = enf.get_compliance_summary()
        assert summary["total_checks"] == 3
        assert summary["compliant"] == 2
        assert summary["non_compliant"] == 1
        assert summary["remediated"] == 0
        assert summary["compliance_rate"] == pytest.approx(2 / 3, abs=1e-4)

    def test_empty_summary(self):
        enf = _enforcer()
        summary = enf.get_compliance_summary()
        assert summary["total_checks"] == 0
        assert summary["compliant"] == 0
        assert summary["non_compliant"] == 0
        assert summary["remediated"] == 0
        assert summary["compliance_rate"] == 0.0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        enf = _enforcer()
        stats = enf.get_stats()
        assert stats["total_policies"] == 0
        assert stats["total_checks"] == 0
        assert stats["total_actions"] == 0
        assert stats["enforcement_mode_distribution"] == {}
        assert stats["check_status_distribution"] == {}

    def test_stats_populated(self):
        enf = _enforcer()
        policy = enf.create_policy(
            "auto-policy",
            required_tags=["team"],
            enforcement_mode=EnforcementMode.AUTO_TAG,
        )
        enf.create_policy("audit-policy", enforcement_mode=EnforcementMode.AUDIT)
        check = enf.check_resource("r-1", existing_tags={}, policy_id=policy.id)
        enf.check_resource("r-2", existing_tags={"team": "a"})
        enf.enforce(check.id)

        stats = enf.get_stats()
        assert stats["total_policies"] == 2
        assert stats["total_checks"] == 2
        assert stats["total_actions"] == 1
        assert stats["enforcement_mode_distribution"][EnforcementMode.AUTO_TAG] == 1
        assert stats["enforcement_mode_distribution"][EnforcementMode.AUDIT] == 1


# ---------------------------------------------------------------------------
# check_resource trims at max_checks
# ---------------------------------------------------------------------------


class TestCheckTrimsAtMax:
    def test_trims(self):
        enf = _enforcer(max_checks=3)
        enf.create_policy("standard", required_tags=["team"])
        for i in range(5):
            enf.check_resource(f"r-{i}", existing_tags={"team": "a"})
        assert len(enf.list_checks()) == 3
