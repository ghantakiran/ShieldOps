"""Tests for shieldops.billing.tag_governance — ResourceTagGovernanceEngine."""

from __future__ import annotations

from shieldops.billing.tag_governance import (
    ComplianceLevel,
    ResourceTagGovernanceEngine,
    ResourceTagReport,
    TagComplianceScore,
    TagPolicy,
    TagPolicyAction,
    TagSource,
)


def _engine(**kw) -> ResourceTagGovernanceEngine:
    return ResourceTagGovernanceEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_action_enforce(self):
        assert TagPolicyAction.ENFORCE == "enforce"

    def test_action_warn(self):
        assert TagPolicyAction.WARN == "warn"

    def test_action_audit(self):
        assert TagPolicyAction.AUDIT == "audit"

    def test_action_auto_tag(self):
        assert TagPolicyAction.AUTO_TAG == "auto_tag"

    def test_compliance_fully(self):
        assert ComplianceLevel.FULLY_COMPLIANT == "fully_compliant"

    def test_compliance_mostly(self):
        assert ComplianceLevel.MOSTLY_COMPLIANT == "mostly_compliant"

    def test_compliance_partially(self):
        assert ComplianceLevel.PARTIALLY_COMPLIANT == "partially_compliant"

    def test_compliance_non(self):
        assert ComplianceLevel.NON_COMPLIANT == "non_compliant"

    def test_source_manual(self):
        assert TagSource.MANUAL == "manual"

    def test_source_auto(self):
        assert TagSource.AUTO_TAGGED == "auto_tagged"

    def test_source_inherited(self):
        assert TagSource.INHERITED == "inherited"

    def test_source_default(self):
        assert TagSource.POLICY_DEFAULT == "policy_default"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_policy_defaults(self):
        p = TagPolicy()
        assert p.id
        assert p.action == TagPolicyAction.ENFORCE
        assert p.required_tags == []

    def test_report_defaults(self):
        r = ResourceTagReport()
        assert r.compliance == ComplianceLevel.NON_COMPLIANT

    def test_score_defaults(self):
        s = TagComplianceScore()
        assert s.total_resources == 0
        assert s.score_pct == 0.0


# ---------------------------------------------------------------------------
# create_policy
# ---------------------------------------------------------------------------


class TestCreatePolicy:
    def test_basic_create(self):
        eng = _engine()
        p = eng.create_policy("mandatory-tags", required_tags=["env", "team"])
        assert p.name == "mandatory-tags"
        assert len(p.required_tags) == 2

    def test_unique_ids(self):
        eng = _engine()
        p1 = eng.create_policy("p1")
        p2 = eng.create_policy("p2")
        assert p1.id != p2.id

    def test_eviction_at_max(self):
        eng = _engine(max_policies=3)
        for i in range(5):
            eng.create_policy(f"p{i}")
        assert len(eng._policies) == 3

    def test_with_defaults(self):
        eng = _engine()
        p = eng.create_policy(
            "auto",
            action=TagPolicyAction.AUTO_TAG,
            default_values={"env": "dev"},
        )
        assert p.default_values == {"env": "dev"}


# ---------------------------------------------------------------------------
# get / list policies
# ---------------------------------------------------------------------------


class TestGetPolicy:
    def test_found(self):
        eng = _engine()
        p = eng.create_policy("test")
        assert eng.get_policy(p.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_policy("nonexistent") is None


class TestListPolicies:
    def test_list(self):
        eng = _engine()
        eng.create_policy("a")
        eng.create_policy("b")
        assert len(eng.list_policies()) == 2


# ---------------------------------------------------------------------------
# evaluate_resource
# ---------------------------------------------------------------------------


class TestEvaluateResource:
    def test_fully_compliant(self):
        eng = _engine()
        eng.create_policy("p1", required_tags=["env"])
        report = eng.evaluate_resource("r1", existing_tags={"env": "prod"})
        assert report.compliance == ComplianceLevel.FULLY_COMPLIANT

    def test_non_compliant(self):
        eng = _engine()
        eng.create_policy("p1", required_tags=["env", "team", "owner", "cost-center"])
        report = eng.evaluate_resource("r1", existing_tags={})
        assert report.compliance == ComplianceLevel.NON_COMPLIANT
        assert len(report.missing_tags) >= 3

    def test_auto_tag(self):
        eng = _engine()
        eng.create_policy(
            "auto",
            required_tags=["env"],
            action=TagPolicyAction.AUTO_TAG,
            default_values={"env": "dev"},
        )
        report = eng.evaluate_resource("r1", existing_tags={})
        assert "env" in report.auto_tagged


# ---------------------------------------------------------------------------
# evaluate_bulk
# ---------------------------------------------------------------------------


class TestEvaluateBulk:
    def test_bulk(self):
        eng = _engine()
        eng.create_policy("p1", required_tags=["env"])
        resources = [
            {"resource_id": "r1", "tags": {"env": "prod"}},
            {"resource_id": "r2", "tags": {}},
        ]
        reports = eng.evaluate_bulk(resources)
        assert len(reports) == 2


# ---------------------------------------------------------------------------
# auto_tag_resource
# ---------------------------------------------------------------------------


class TestAutoTagResource:
    def test_auto_tag(self):
        eng = _engine()
        eng.create_policy(
            "auto",
            required_tags=["env"],
            action=TagPolicyAction.AUTO_TAG,
            default_values={"env": "dev"},
        )
        applied = eng.auto_tag_resource("r1")
        assert applied == {"env": "dev"}

    def test_no_auto_tag(self):
        eng = _engine()
        eng.create_policy("enforce", required_tags=["env"])
        applied = eng.auto_tag_resource("r1")
        assert applied == {}


# ---------------------------------------------------------------------------
# compliance score / untagged / stats
# ---------------------------------------------------------------------------


class TestComplianceScore:
    def test_empty_score(self):
        eng = _engine()
        score = eng.get_compliance_score()
        assert score.total_resources == 0

    def test_computed_score(self):
        eng = _engine()
        eng.create_policy("p1", required_tags=["env"])
        eng.evaluate_resource("r1", existing_tags={"env": "prod"})
        eng.evaluate_resource("r2", existing_tags={})
        score = eng.get_compliance_score()
        assert score.total_resources == 2
        assert score.score_pct == 50.0


class TestUntaggedResources:
    def test_untagged(self):
        eng = _engine()
        eng.create_policy("p1", required_tags=["env", "team", "owner", "cost"])
        eng.evaluate_resource("r1", existing_tags={})
        untagged = eng.get_untagged_resources()
        assert len(untagged) == 1


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_policies"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.create_policy("p1", required_tags=["env"])
        eng.evaluate_resource("r1", existing_tags={"env": "prod"})
        stats = eng.get_stats()
        assert stats["total_policies"] == 1
        assert stats["total_reports"] == 1
