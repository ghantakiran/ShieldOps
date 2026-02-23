"""Tests for shieldops.compliance.license_scanner — DependencyLicenseScanner."""

from __future__ import annotations

from shieldops.compliance.license_scanner import (
    DependencyLicense,
    DependencyLicenseScanner,
    LicenseCategory,
    LicensePolicy,
    LicenseRisk,
    LicenseViolation,
    PolicyAction,
)


def _engine(**kw) -> DependencyLicenseScanner:
    return DependencyLicenseScanner(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_permissive(self):
        assert LicenseCategory.PERMISSIVE == "permissive"

    def test_category_weak_copyleft(self):
        assert LicenseCategory.WEAK_COPYLEFT == "weak_copyleft"

    def test_category_strong_copyleft(self):
        assert LicenseCategory.STRONG_COPYLEFT == "strong_copyleft"

    def test_category_proprietary(self):
        assert LicenseCategory.PROPRIETARY == "proprietary"

    def test_category_unknown(self):
        assert LicenseCategory.UNKNOWN == "unknown"

    def test_risk_low(self):
        assert LicenseRisk.LOW == "low"

    def test_risk_medium(self):
        assert LicenseRisk.MEDIUM == "medium"

    def test_risk_high(self):
        assert LicenseRisk.HIGH == "high"

    def test_risk_critical(self):
        assert LicenseRisk.CRITICAL == "critical"

    def test_action_allow(self):
        assert PolicyAction.ALLOW == "allow"

    def test_action_warn(self):
        assert PolicyAction.WARN == "warn"

    def test_action_block(self):
        assert PolicyAction.BLOCK == "block"

    def test_action_review(self):
        assert PolicyAction.REVIEW == "review"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_dependency_defaults(self):
        dep = DependencyLicense(name="requests")
        assert dep.id
        assert dep.name == "requests"
        assert dep.category == LicenseCategory.UNKNOWN
        assert dep.risk == LicenseRisk.LOW
        assert dep.version == ""
        assert dep.spdx_id == ""
        assert dep.project == ""

    def test_policy_defaults(self):
        policy = LicensePolicy(name="block-gpl")
        assert policy.id
        assert policy.action == PolicyAction.ALLOW
        assert policy.spdx_pattern == ""
        assert policy.category is None

    def test_violation_defaults(self):
        v = LicenseViolation(dependency_id="d-1", policy_id="p-1")
        assert v.id
        assert v.action == PolicyAction.BLOCK
        assert v.dependency_name == ""
        assert v.project == ""


# ---------------------------------------------------------------------------
# register_dependency
# ---------------------------------------------------------------------------


class TestRegisterDependency:
    def test_basic_register(self):
        eng = _engine()
        dep = eng.register_dependency("requests", spdx_id="MIT")
        assert dep.name == "requests"
        assert dep.category == LicenseCategory.PERMISSIVE
        assert dep.risk == LicenseRisk.LOW

    def test_gpl_classified(self):
        eng = _engine()
        dep = eng.register_dependency("lib-x", spdx_id="GPL-3.0")
        assert dep.category == LicenseCategory.STRONG_COPYLEFT
        assert dep.risk == LicenseRisk.HIGH

    def test_unknown_license(self):
        eng = _engine()
        dep = eng.register_dependency("lib-y", spdx_id="CustomLicense")
        assert dep.category == LicenseCategory.UNKNOWN
        assert dep.risk == LicenseRisk.MEDIUM

    def test_with_version_and_project(self):
        eng = _engine()
        dep = eng.register_dependency(
            "flask", version="3.0.0", spdx_id="BSD-3-Clause", project="app"
        )
        assert dep.version == "3.0.0"
        assert dep.project == "app"
        assert dep.category == LicenseCategory.PERMISSIVE

    def test_evicts_at_max(self):
        eng = _engine(max_dependencies=2)
        d1 = eng.register_dependency("lib-1")
        eng.register_dependency("lib-2")
        eng.register_dependency("lib-3")
        result = [d for d in eng.list_dependencies() if d.id == d1.id]
        assert len(result) == 0


# ---------------------------------------------------------------------------
# classify_license / assess_risk
# ---------------------------------------------------------------------------


class TestClassify:
    def test_classify_mit(self):
        eng = _engine()
        assert eng.classify_license("MIT") == LicenseCategory.PERMISSIVE

    def test_classify_apache(self):
        eng = _engine()
        assert eng.classify_license("Apache-2.0") == LicenseCategory.PERMISSIVE

    def test_classify_bsd_2_clause(self):
        eng = _engine()
        assert eng.classify_license("BSD-2-Clause") == LicenseCategory.PERMISSIVE

    def test_classify_lgpl(self):
        eng = _engine()
        assert eng.classify_license("LGPL-3.0") == LicenseCategory.WEAK_COPYLEFT

    def test_classify_mpl(self):
        eng = _engine()
        assert eng.classify_license("MPL-2.0") == LicenseCategory.WEAK_COPYLEFT

    def test_classify_agpl(self):
        eng = _engine()
        assert eng.classify_license("AGPL-3.0") == LicenseCategory.STRONG_COPYLEFT

    def test_classify_unknown(self):
        eng = _engine()
        assert eng.classify_license("FooBar") == LicenseCategory.UNKNOWN

    def test_assess_risk_permissive(self):
        eng = _engine()
        assert eng.assess_risk("MIT") == LicenseRisk.LOW

    def test_assess_risk_copyleft(self):
        eng = _engine()
        assert eng.assess_risk("GPL-3.0") == LicenseRisk.HIGH

    def test_assess_risk_weak_copyleft(self):
        eng = _engine()
        assert eng.assess_risk("LGPL-3.0") == LicenseRisk.MEDIUM

    def test_assess_risk_unknown(self):
        eng = _engine()
        assert eng.assess_risk("SomeUnknown") == LicenseRisk.MEDIUM


# ---------------------------------------------------------------------------
# create_policy / evaluate_project
# ---------------------------------------------------------------------------


class TestCreatePolicy:
    def test_basic_policy(self):
        eng = _engine()
        policy = eng.create_policy(
            "block-gpl", category=LicenseCategory.STRONG_COPYLEFT, action=PolicyAction.BLOCK
        )
        assert policy.name == "block-gpl"
        assert policy.action == PolicyAction.BLOCK

    def test_policy_with_spdx_pattern(self):
        eng = _engine()
        policy = eng.create_policy("warn-gpl", spdx_pattern="GPL", action=PolicyAction.WARN)
        assert policy.spdx_pattern == "GPL"

    def test_list_policies(self):
        eng = _engine()
        eng.create_policy("p1", action=PolicyAction.ALLOW)
        eng.create_policy("p2", action=PolicyAction.BLOCK)
        assert len(eng.list_policies()) == 2


class TestEvaluateProject:
    def test_no_violations(self):
        eng = _engine()
        eng.register_dependency("requests", spdx_id="MIT", project="my-app")
        eng.create_policy(
            "block-gpl", category=LicenseCategory.STRONG_COPYLEFT, action=PolicyAction.BLOCK
        )
        violations = eng.evaluate_project("my-app")
        assert len(violations) == 0

    def test_violation_found(self):
        eng = _engine()
        eng.register_dependency("gpl-lib", spdx_id="GPL-3.0", project="my-app")
        eng.create_policy(
            "block-copyleft", category=LicenseCategory.STRONG_COPYLEFT, action=PolicyAction.BLOCK
        )
        violations = eng.evaluate_project("my-app")
        assert len(violations) == 1
        assert violations[0].action == PolicyAction.BLOCK

    def test_warn_violation(self):
        eng = _engine()
        eng.register_dependency("lgpl-lib", spdx_id="LGPL-3.0", project="my-app")
        eng.create_policy(
            "warn-weak", category=LicenseCategory.WEAK_COPYLEFT, action=PolicyAction.WARN
        )
        violations = eng.evaluate_project("my-app")
        assert len(violations) == 1
        assert violations[0].action == PolicyAction.WARN

    def test_allow_policy_no_violation(self):
        eng = _engine()
        eng.register_dependency("gpl-lib", spdx_id="GPL-3.0", project="my-app")
        eng.create_policy(
            "allow-copyleft", category=LicenseCategory.STRONG_COPYLEFT, action=PolicyAction.ALLOW
        )
        violations = eng.evaluate_project("my-app")
        assert len(violations) == 0

    def test_spdx_pattern_match(self):
        eng = _engine()
        eng.register_dependency("gpl-lib", spdx_id="GPL-3.0", project="my-app")
        eng.create_policy("block-gpl-pattern", spdx_pattern="GPL", action=PolicyAction.BLOCK)
        violations = eng.evaluate_project("my-app")
        assert len(violations) == 1


# ---------------------------------------------------------------------------
# list_dependencies / violations / policies / stats
# ---------------------------------------------------------------------------


class TestListDependencies:
    def test_filter_by_project(self):
        eng = _engine()
        eng.register_dependency("lib-a", project="proj-1")
        eng.register_dependency("lib-b", project="proj-2")
        results = eng.list_dependencies(project="proj-1")
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.register_dependency("lib-a", spdx_id="MIT")
        eng.register_dependency("lib-b", spdx_id="GPL-3.0")
        results = eng.list_dependencies(category=LicenseCategory.PERMISSIVE)
        assert len(results) == 1

    def test_list_all(self):
        eng = _engine()
        eng.register_dependency("lib-a")
        eng.register_dependency("lib-b")
        assert len(eng.list_dependencies()) == 2


class TestListViolations:
    def test_filter_by_project(self):
        eng = _engine()
        eng.register_dependency("gpl-lib", spdx_id="GPL-3.0", project="my-app")
        eng.create_policy(
            "block", category=LicenseCategory.STRONG_COPYLEFT, action=PolicyAction.BLOCK
        )
        eng.evaluate_project("my-app")
        results = eng.list_violations(project="my-app")
        assert len(results) == 1

    def test_filter_by_action(self):
        eng = _engine()
        eng.register_dependency("gpl-lib", spdx_id="GPL-3.0", project="app")
        eng.create_policy(
            "block", category=LicenseCategory.STRONG_COPYLEFT, action=PolicyAction.BLOCK
        )
        eng.evaluate_project("app")
        results = eng.list_violations(action=PolicyAction.WARN)
        assert len(results) == 0


class TestGetPolicy:
    def test_get_existing(self):
        eng = _engine()
        policy = eng.create_policy("p1")
        assert eng.get_policy(policy.id) is not None

    def test_get_nonexistent(self):
        eng = _engine()
        assert eng.get_policy("nonexistent") is None


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_dependencies"] == 0
        assert stats["total_policies"] == 0
        assert stats["total_violations"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.register_dependency("requests", spdx_id="MIT")
        eng.register_dependency("flask", spdx_id="BSD-3-Clause")
        stats = eng.get_stats()
        assert stats["total_dependencies"] == 2
        assert stats["category_distribution"][LicenseCategory.PERMISSIVE] == 2

    def test_risk_distribution(self):
        eng = _engine()
        eng.register_dependency("requests", spdx_id="MIT")
        eng.register_dependency("gpl-lib", spdx_id="GPL-3.0")
        stats = eng.get_stats()
        assert stats["risk_distribution"][LicenseRisk.LOW] == 1
        assert stats["risk_distribution"][LicenseRisk.HIGH] == 1
