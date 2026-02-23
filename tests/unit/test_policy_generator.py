"""Tests for shieldops.policy.policy_generator — PolicyCodeGenerator."""

from __future__ import annotations

import pytest

from shieldops.policy.policy_generator import (
    GeneratedPolicy,
    PolicyCategory,
    PolicyCodeGenerator,
    PolicyRequirement,
    PolicySeverity,
)


def _generator(**kw) -> PolicyCodeGenerator:
    return PolicyCodeGenerator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # PolicyCategory (5 values)

    def test_category_security(self):
        assert PolicyCategory.SECURITY == "security"

    def test_category_compliance(self):
        assert PolicyCategory.COMPLIANCE == "compliance"

    def test_category_cost(self):
        assert PolicyCategory.COST == "cost"

    def test_category_operational(self):
        assert PolicyCategory.OPERATIONAL == "operational"

    def test_category_custom(self):
        assert PolicyCategory.CUSTOM == "custom"

    # PolicySeverity (4 values)

    def test_severity_info(self):
        assert PolicySeverity.INFO == "info"

    def test_severity_warning(self):
        assert PolicySeverity.WARNING == "warning"

    def test_severity_error(self):
        assert PolicySeverity.ERROR == "error"

    def test_severity_critical(self):
        assert PolicySeverity.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_policy_requirement_defaults(self):
        req = PolicyRequirement()
        assert req.id
        assert req.description == ""
        assert req.category == PolicyCategory.CUSTOM
        assert req.severity == PolicySeverity.WARNING
        assert req.conditions == []
        assert req.created_by == ""
        assert req.created_at > 0

    def test_generated_policy_defaults(self):
        pol = GeneratedPolicy()
        assert pol.id
        assert pol.requirement_id == ""
        assert pol.name == ""
        assert pol.rego_code == ""
        assert pol.category == PolicyCategory.CUSTOM
        assert pol.severity == PolicySeverity.WARNING
        assert pol.version == 1
        assert pol.is_active is False
        assert pol.validated is False
        assert pol.created_at > 0
        assert pol.updated_at is None


# ---------------------------------------------------------------------------
# create_requirement
# ---------------------------------------------------------------------------


class TestCreateRequirement:
    def test_basic_create(self):
        g = _generator()
        req = g.create_requirement(
            "No public S3 buckets",
            PolicyCategory.SECURITY,
        )
        assert req.description == "No public S3 buckets"
        assert req.category == PolicyCategory.SECURITY

    def test_create_with_conditions(self):
        g = _generator()
        req = g.create_requirement(
            "Enforce encryption",
            PolicyCategory.COMPLIANCE,
            conditions=["encryption_enabled", "tls_1_2"],
            severity=PolicySeverity.CRITICAL,
        )
        assert req.conditions == ["encryption_enabled", "tls_1_2"]
        assert req.severity == PolicySeverity.CRITICAL

    def test_evicts_at_max(self):
        g = _generator(max_requirements=2)
        r1 = g.create_requirement("First", PolicyCategory.CUSTOM)
        g.create_requirement("Second", PolicyCategory.CUSTOM)
        g.create_requirement("Third", PolicyCategory.CUSTOM)
        assert len(g._requirements) == 2
        assert g.get_requirement(r1.id) is None

    def test_filter_by_category(self):
        g = _generator()
        g.create_requirement("Sec", PolicyCategory.SECURITY)
        g.create_requirement("Cost", PolicyCategory.COST)
        sec = g.list_requirements(category=PolicyCategory.SECURITY)
        assert len(sec) == 1
        assert sec[0].category == PolicyCategory.SECURITY


# ---------------------------------------------------------------------------
# generate_policy
# ---------------------------------------------------------------------------


class TestGeneratePolicy:
    def test_basic_generate_contains_package(self):
        g = _generator()
        req = g.create_requirement(
            "No public access",
            PolicyCategory.SECURITY,
        )
        pol = g.generate_policy(req.id, "no-public-access")
        assert "package shieldops.no_public_access" in (pol.rego_code)

    def test_generate_contains_conditions(self):
        g = _generator()
        req = g.create_requirement(
            "Enforce encryption",
            PolicyCategory.COMPLIANCE,
            conditions=["encryption_enabled"],
        )
        pol = g.generate_policy(req.id, "encrypt-check")
        assert "encryption_enabled" in pol.rego_code

    def test_generate_raises_for_missing_requirement(self):
        g = _generator()
        with pytest.raises(ValueError, match="Requirement not found"):
            g.generate_policy("nonexistent", "test")

    def test_generate_sets_category_and_severity(self):
        g = _generator()
        req = g.create_requirement(
            "Check cost",
            PolicyCategory.COST,
            severity=PolicySeverity.ERROR,
        )
        pol = g.generate_policy(req.id, "cost-check")
        assert pol.category == PolicyCategory.COST
        assert pol.severity == PolicySeverity.ERROR

    def test_generate_contains_allow_rule(self):
        g = _generator()
        req = g.create_requirement("Default", PolicyCategory.CUSTOM)
        pol = g.generate_policy(req.id, "default-rule")
        assert "allow" in pol.rego_code

    def test_generate_evicts_at_max_policies(self):
        g = _generator(max_policies=2)
        r1 = g.create_requirement("A", PolicyCategory.CUSTOM)
        r2 = g.create_requirement("B", PolicyCategory.CUSTOM)
        r3 = g.create_requirement("C", PolicyCategory.CUSTOM)
        p1 = g.generate_policy(r1.id, "pol-a")
        g.generate_policy(r2.id, "pol-b")
        g.generate_policy(r3.id, "pol-c")
        assert len(g._policies) == 2
        assert g.get_policy(p1.id) is None


# ---------------------------------------------------------------------------
# validate_policy
# ---------------------------------------------------------------------------


class TestValidatePolicy:
    def test_valid_policy_passes(self):
        g = _generator()
        req = g.create_requirement("Test", PolicyCategory.SECURITY)
        pol = g.generate_policy(req.id, "test-policy")
        result = g.validate_policy(pol.id)
        assert result["valid"] is True
        assert result["errors"] == []
        assert pol.validated is True

    def test_missing_package_fails(self):
        g = _generator()
        req = g.create_requirement("Test", PolicyCategory.CUSTOM)
        pol = g.generate_policy(req.id, "test")
        pol.rego_code = "allow { true }"
        result = g.validate_policy(pol.id)
        assert result["valid"] is False
        assert any("package" in e for e in result["errors"])

    def test_missing_rules_fails(self):
        g = _generator()
        req = g.create_requirement("Test", PolicyCategory.CUSTOM)
        pol = g.generate_policy(req.id, "test")
        pol.rego_code = "package shieldops.test"
        result = g.validate_policy(pol.id)
        assert result["valid"] is False
        assert any("rule" in e for e in result["errors"])

    def test_policy_not_found(self):
        g = _generator()
        result = g.validate_policy("nonexistent")
        assert result["valid"] is False


# ---------------------------------------------------------------------------
# policy lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_activate_policy(self):
        g = _generator()
        req = g.create_requirement("Test", PolicyCategory.SECURITY)
        pol = g.generate_policy(req.id, "activate-test")
        result = g.activate_policy(pol.id)
        assert result is not None
        assert result.is_active is True
        assert result.updated_at is not None

    def test_deactivate_policy(self):
        g = _generator()
        req = g.create_requirement("Test", PolicyCategory.SECURITY)
        pol = g.generate_policy(req.id, "deactivate-test")
        g.activate_policy(pol.id)
        result = g.deactivate_policy(pol.id)
        assert result is not None
        assert result.is_active is False
        assert result.updated_at is not None

    def test_activate_not_found(self):
        g = _generator()
        assert g.activate_policy("fake") is None

    def test_deactivate_not_found(self):
        g = _generator()
        assert g.deactivate_policy("fake") is None

    def test_update_policy_increments_version(self):
        g = _generator()
        req = g.create_requirement("Test", PolicyCategory.CUSTOM)
        pol = g.generate_policy(req.id, "update-test")
        assert pol.version == 1
        result = g.update_policy(pol.id, "package new\nallow { true }")
        assert result is not None
        assert result.version == 2
        assert result.validated is False
        assert result.updated_at is not None

    def test_update_not_found(self):
        g = _generator()
        assert g.update_policy("fake", "code") is None


# ---------------------------------------------------------------------------
# list_policies
# ---------------------------------------------------------------------------


class TestListPolicies:
    def test_filter_by_category(self):
        g = _generator()
        r1 = g.create_requirement("Sec", PolicyCategory.SECURITY)
        r2 = g.create_requirement("Cost", PolicyCategory.COST)
        g.generate_policy(r1.id, "sec-pol")
        g.generate_policy(r2.id, "cost-pol")
        sec = g.list_policies(category=PolicyCategory.SECURITY)
        assert len(sec) == 1
        assert sec[0].category == PolicyCategory.SECURITY

    def test_filter_active_only(self):
        g = _generator()
        r1 = g.create_requirement("A", PolicyCategory.CUSTOM)
        r2 = g.create_requirement("B", PolicyCategory.CUSTOM)
        p1 = g.generate_policy(r1.id, "pol-a")
        g.generate_policy(r2.id, "pol-b")
        g.activate_policy(p1.id)
        active = g.list_policies(active_only=True)
        assert len(active) == 1
        assert active[0].id == p1.id

    def test_list_all(self):
        g = _generator()
        r1 = g.create_requirement("A", PolicyCategory.CUSTOM)
        r2 = g.create_requirement("B", PolicyCategory.CUSTOM)
        g.generate_policy(r1.id, "pol-a")
        g.generate_policy(r2.id, "pol-b")
        assert len(g.list_policies()) == 2


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        g = _generator()
        stats = g.get_stats()
        assert stats["total_requirements"] == 0
        assert stats["total_policies"] == 0
        assert stats["active_policies"] == 0
        assert stats["validated_policies"] == 0

    def test_populated_stats(self):
        g = _generator()
        r1 = g.create_requirement(
            "Sec",
            PolicyCategory.SECURITY,
            severity=PolicySeverity.CRITICAL,
        )
        r2 = g.create_requirement(
            "Cost",
            PolicyCategory.COST,
            severity=PolicySeverity.WARNING,
        )
        p1 = g.generate_policy(r1.id, "sec-pol")
        p2 = g.generate_policy(r2.id, "cost-pol")
        g.activate_policy(p1.id)
        g.validate_policy(p2.id)
        stats = g.get_stats()
        assert stats["total_requirements"] == 2
        assert stats["total_policies"] == 2
        assert stats["active_policies"] == 1
        assert stats["validated_policies"] == 1
        by_cat = stats["policies_by_category"]
        assert by_cat["security"] == 1
        assert by_cat["cost"] == 1
        by_sev = stats["policies_by_severity"]
        assert by_sev["critical"] == 1
        assert by_sev["warning"] == 1
