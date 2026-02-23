"""Tests for shieldops.analytics.tagging_compliance -- TaggingComplianceEngine."""

from __future__ import annotations

import pytest

from shieldops.analytics.tagging_compliance import (
    ResourceProvider,
    ResourceTagRecord,
    TagComplianceReport,
    TagComplianceStatus,
    TaggingComplianceEngine,
    TagPolicy,
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _engine(**kwargs) -> TaggingComplianceEngine:
    return TaggingComplianceEngine(**kwargs)


def _engine_with_policy(
    required: list[str] | None = None,
    allowed_values: dict[str, list[str]] | None = None,
    provider: ResourceProvider | None = None,
) -> tuple[TaggingComplianceEngine, TagPolicy]:
    eng = _engine()
    pol = eng.create_policy(
        name="default",
        required_tags=required or ["env", "owner"],
        allowed_values=allowed_values,
        provider=provider,
    )
    return eng, pol


# -------------------------------------------------------------------
# Enum values
# -------------------------------------------------------------------


class TestEnums:
    def test_compliance_status_compliant(self):
        assert TagComplianceStatus.COMPLIANT == "compliant"

    def test_compliance_status_non_compliant(self):
        assert TagComplianceStatus.NON_COMPLIANT == "non_compliant"

    def test_compliance_status_partially_compliant(self):
        assert TagComplianceStatus.PARTIALLY_COMPLIANT == "partially_compliant"

    def test_compliance_status_exempt(self):
        assert TagComplianceStatus.EXEMPT == "exempt"

    def test_provider_aws(self):
        assert ResourceProvider.AWS == "aws"

    def test_provider_gcp(self):
        assert ResourceProvider.GCP == "gcp"

    def test_provider_azure(self):
        assert ResourceProvider.AZURE == "azure"

    def test_provider_kubernetes(self):
        assert ResourceProvider.KUBERNETES == "kubernetes"

    def test_provider_on_prem(self):
        assert ResourceProvider.ON_PREM == "on_prem"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_tag_policy_defaults(self):
        p = TagPolicy(name="test", required_tags=["env"])
        assert p.id
        assert p.name == "test"
        assert p.required_tags == ["env"]
        assert p.optional_tags == []
        assert p.allowed_values == {}
        assert p.provider is None
        assert p.created_at > 0

    def test_tag_policy_with_all_fields(self):
        p = TagPolicy(
            name="full",
            required_tags=["env"],
            optional_tags=["cost-center"],
            allowed_values={"env": ["prod", "dev"]},
            provider=ResourceProvider.AWS,
        )
        assert p.provider == ResourceProvider.AWS
        assert "cost-center" in p.optional_tags
        assert p.allowed_values["env"] == ["prod", "dev"]

    def test_resource_tag_record_defaults(self):
        r = ResourceTagRecord(
            resource_id="r-1",
            resource_type="ec2",
            provider=ResourceProvider.AWS,
        )
        assert r.id
        assert r.tags == {}
        assert r.missing_tags == []
        assert r.invalid_tags == []
        assert r.status == TagComplianceStatus.NON_COMPLIANT
        assert r.scanned_at > 0

    def test_tag_compliance_report_defaults(self):
        rpt = TagComplianceReport()
        assert rpt.total_resources == 0
        assert rpt.compliant == 0
        assert rpt.non_compliant == 0
        assert rpt.partially_compliant == 0
        assert rpt.compliance_pct == 0.0
        assert rpt.top_missing_tags == []


# -------------------------------------------------------------------
# Create policy
# -------------------------------------------------------------------


class TestCreatePolicy:
    def test_create_basic(self):
        eng = _engine()
        p = eng.create_policy(name="basics", required_tags=["env"])
        assert p.name == "basics"
        assert p.required_tags == ["env"]
        assert p.id

    def test_create_with_optional_tags(self):
        eng = _engine()
        p = eng.create_policy(
            name="opt",
            required_tags=["env"],
            optional_tags=["team"],
        )
        assert p.optional_tags == ["team"]

    def test_create_with_allowed_values(self):
        eng = _engine()
        p = eng.create_policy(
            name="vals",
            required_tags=["env"],
            allowed_values={"env": ["prod", "dev"]},
        )
        assert p.allowed_values["env"] == ["prod", "dev"]

    def test_create_with_provider(self):
        eng = _engine()
        p = eng.create_policy(
            name="aws-only",
            required_tags=["env"],
            provider=ResourceProvider.AWS,
        )
        assert p.provider == ResourceProvider.AWS

    def test_create_multiple(self):
        eng = _engine()
        eng.create_policy(name="p1", required_tags=["env"])
        eng.create_policy(name="p2", required_tags=["owner"])
        assert len(eng.list_policies()) == 2

    def test_create_policy_exceeds_limit(self):
        eng = _engine(max_policies=2)
        eng.create_policy(name="p1", required_tags=["env"])
        eng.create_policy(name="p2", required_tags=["owner"])
        with pytest.raises(ValueError, match="Maximum policies limit"):
            eng.create_policy(name="p3", required_tags=["tier"])


# -------------------------------------------------------------------
# Scan resource
# -------------------------------------------------------------------


class TestScanResource:
    def test_scan_compliant_resource(self):
        eng, _ = _engine_with_policy(required=["env", "owner"])
        rec = eng.scan_resource(
            resource_id="i-123",
            resource_type="ec2",
            provider=ResourceProvider.AWS,
            tags={"env": "prod", "owner": "sre"},
        )
        assert rec.status == TagComplianceStatus.COMPLIANT
        assert rec.missing_tags == []
        assert rec.invalid_tags == []

    def test_scan_non_compliant_all_missing(self):
        eng, _ = _engine_with_policy(required=["env", "owner"])
        rec = eng.scan_resource(
            resource_id="i-456",
            resource_type="ec2",
            provider=ResourceProvider.AWS,
            tags={},
        )
        assert rec.status == TagComplianceStatus.NON_COMPLIANT
        assert "env" in rec.missing_tags
        assert "owner" in rec.missing_tags

    def test_scan_partially_compliant(self):
        eng, _ = _engine_with_policy(required=["env", "owner"])
        rec = eng.scan_resource(
            resource_id="i-789",
            resource_type="ec2",
            provider=ResourceProvider.AWS,
            tags={"env": "prod"},
        )
        assert rec.status == TagComplianceStatus.PARTIALLY_COMPLIANT
        assert "owner" in rec.missing_tags

    def test_scan_invalid_allowed_value(self):
        eng, _ = _engine_with_policy(
            required=["env"],
            allowed_values={"env": ["prod", "dev"]},
        )
        rec = eng.scan_resource(
            resource_id="i-bad",
            resource_type="ec2",
            provider=ResourceProvider.AWS,
            tags={"env": "staging"},
        )
        assert rec.status == TagComplianceStatus.NON_COMPLIANT
        assert "env" in rec.invalid_tags

    def test_scan_valid_allowed_value(self):
        eng, _ = _engine_with_policy(
            required=["env"],
            allowed_values={"env": ["prod", "dev"]},
        )
        rec = eng.scan_resource(
            resource_id="i-good",
            resource_type="ec2",
            provider=ResourceProvider.AWS,
            tags={"env": "prod"},
        )
        assert rec.status == TagComplianceStatus.COMPLIANT

    def test_scan_provider_specific_policy_match(self):
        eng = _engine()
        eng.create_policy(
            name="aws-only",
            required_tags=["cost-center"],
            provider=ResourceProvider.AWS,
        )
        rec = eng.scan_resource(
            resource_id="i-aws",
            resource_type="ec2",
            provider=ResourceProvider.AWS,
            tags={},
        )
        assert "cost-center" in rec.missing_tags

    def test_scan_provider_specific_policy_no_match(self):
        eng = _engine()
        eng.create_policy(
            name="aws-only",
            required_tags=["cost-center"],
            provider=ResourceProvider.AWS,
        )
        rec = eng.scan_resource(
            resource_id="vm-gcp",
            resource_type="vm",
            provider=ResourceProvider.GCP,
            tags={},
        )
        # AWS-only policy should not apply to GCP
        assert rec.status == TagComplianceStatus.COMPLIANT

    def test_scan_global_policy_applies_to_all(self):
        eng = _engine()
        eng.create_policy(
            name="global",
            required_tags=["owner"],
            provider=None,
        )
        rec = eng.scan_resource(
            resource_id="res-1",
            resource_type="vm",
            provider=ResourceProvider.AZURE,
            tags={},
        )
        assert "owner" in rec.missing_tags

    def test_scan_records_stored(self):
        eng, _ = _engine_with_policy(required=["env"])
        eng.scan_resource(
            resource_id="i-1",
            resource_type="ec2",
            provider=ResourceProvider.AWS,
            tags={"env": "prod"},
        )
        assert len(eng.list_records()) == 1

    def test_scan_exceeds_records_limit(self):
        eng = _engine(max_records=2)
        eng.create_policy(name="p", required_tags=["env"])
        eng.scan_resource("r1", "ec2", ResourceProvider.AWS, {"env": "a"})
        eng.scan_resource("r2", "ec2", ResourceProvider.AWS, {"env": "b"})
        with pytest.raises(ValueError, match="Maximum records limit"):
            eng.scan_resource(
                "r3",
                "ec2",
                ResourceProvider.AWS,
                {"env": "c"},
            )

    def test_scan_no_policies_is_compliant(self):
        eng = _engine()
        rec = eng.scan_resource(
            resource_id="i-none",
            resource_type="ec2",
            provider=ResourceProvider.AWS,
            tags={},
        )
        assert rec.status == TagComplianceStatus.COMPLIANT


# -------------------------------------------------------------------
# Get record
# -------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng, _ = _engine_with_policy(required=["env"])
        eng.scan_resource(
            "i-1",
            "ec2",
            ResourceProvider.AWS,
            {"env": "prod"},
        )
        assert eng.get_record("i-1") is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None

    def test_returns_correct_resource(self):
        eng, _ = _engine_with_policy(required=["env"])
        eng.scan_resource(
            "i-1",
            "ec2",
            ResourceProvider.AWS,
            {"env": "prod"},
        )
        eng.scan_resource(
            "i-2",
            "rds",
            ResourceProvider.AWS,
            {},
        )
        rec = eng.get_record("i-2")
        assert rec is not None
        assert rec.resource_id == "i-2"
        assert rec.resource_type == "rds"


# -------------------------------------------------------------------
# List records
# -------------------------------------------------------------------


class TestListRecords:
    def test_list_empty(self):
        eng = _engine()
        assert eng.list_records() == []

    def test_list_all(self):
        eng, _ = _engine_with_policy(required=["env"])
        eng.scan_resource(
            "r1",
            "ec2",
            ResourceProvider.AWS,
            {"env": "prod"},
        )
        eng.scan_resource(
            "r2",
            "ec2",
            ResourceProvider.GCP,
            {},
        )
        assert len(eng.list_records()) == 2

    def test_filter_by_status(self):
        eng, _ = _engine_with_policy(required=["env"])
        eng.scan_resource(
            "r1",
            "ec2",
            ResourceProvider.AWS,
            {"env": "prod"},
        )
        eng.scan_resource(
            "r2",
            "ec2",
            ResourceProvider.AWS,
            {},
        )
        compliant = eng.list_records(
            status=TagComplianceStatus.COMPLIANT,
        )
        assert len(compliant) == 1
        assert compliant[0].resource_id == "r1"

    def test_filter_by_provider(self):
        eng, _ = _engine_with_policy(required=["env"])
        eng.scan_resource(
            "r1",
            "ec2",
            ResourceProvider.AWS,
            {"env": "prod"},
        )
        eng.scan_resource(
            "r2",
            "vm",
            ResourceProvider.GCP,
            {"env": "prod"},
        )
        aws = eng.list_records(provider=ResourceProvider.AWS)
        assert len(aws) == 1
        assert aws[0].resource_id == "r1"

    def test_filter_by_status_and_provider(self):
        eng, _ = _engine_with_policy(required=["env"])
        eng.scan_resource(
            "r1",
            "ec2",
            ResourceProvider.AWS,
            {},
        )
        eng.scan_resource(
            "r2",
            "vm",
            ResourceProvider.GCP,
            {},
        )
        result = eng.list_records(
            status=TagComplianceStatus.NON_COMPLIANT,
            provider=ResourceProvider.GCP,
        )
        assert len(result) == 1
        assert result[0].resource_id == "r2"


# -------------------------------------------------------------------
# Compliance report
# -------------------------------------------------------------------


class TestComplianceReport:
    def test_empty_report(self):
        eng = _engine()
        rpt = eng.get_compliance_report()
        assert rpt.total_resources == 0
        assert rpt.compliance_pct == 0.0

    def test_all_compliant(self):
        eng, _ = _engine_with_policy(required=["env"])
        eng.scan_resource(
            "r1",
            "ec2",
            ResourceProvider.AWS,
            {"env": "prod"},
        )
        eng.scan_resource(
            "r2",
            "vm",
            ResourceProvider.GCP,
            {"env": "dev"},
        )
        rpt = eng.get_compliance_report()
        assert rpt.total_resources == 2
        assert rpt.compliant == 2
        assert rpt.compliance_pct == 100.0

    def test_mixed_compliance(self):
        eng, _ = _engine_with_policy(required=["env"])
        eng.scan_resource(
            "r1",
            "ec2",
            ResourceProvider.AWS,
            {"env": "prod"},
        )
        eng.scan_resource(
            "r2",
            "vm",
            ResourceProvider.AWS,
            {},
        )
        rpt = eng.get_compliance_report()
        assert rpt.compliant == 1
        assert rpt.non_compliant == 1
        assert rpt.compliance_pct == 50.0

    def test_report_filter_by_provider(self):
        eng, _ = _engine_with_policy(required=["env"])
        eng.scan_resource(
            "r1",
            "ec2",
            ResourceProvider.AWS,
            {"env": "prod"},
        )
        eng.scan_resource(
            "r2",
            "vm",
            ResourceProvider.GCP,
            {},
        )
        rpt = eng.get_compliance_report(provider=ResourceProvider.AWS)
        assert rpt.total_resources == 1
        assert rpt.compliant == 1

    def test_top_missing_tags(self):
        eng, _ = _engine_with_policy(required=["env", "owner", "tier"])
        eng.scan_resource(
            "r1",
            "ec2",
            ResourceProvider.AWS,
            {},
        )
        eng.scan_resource(
            "r2",
            "vm",
            ResourceProvider.AWS,
            {"env": "prod"},
        )
        rpt = eng.get_compliance_report()
        # "env" missing 1x, "owner" missing 2x, "tier" missing 2x
        assert "owner" in rpt.top_missing_tags
        assert "tier" in rpt.top_missing_tags


# -------------------------------------------------------------------
# List / delete policies
# -------------------------------------------------------------------


class TestPolicyManagement:
    def test_list_policies_empty(self):
        eng = _engine()
        assert eng.list_policies() == []

    def test_list_policies_returns_all(self):
        eng = _engine()
        eng.create_policy(name="p1", required_tags=["env"])
        eng.create_policy(name="p2", required_tags=["owner"])
        assert len(eng.list_policies()) == 2

    def test_delete_policy_success(self):
        eng = _engine()
        p = eng.create_policy(name="p1", required_tags=["env"])
        assert eng.delete_policy(p.id) is True
        assert len(eng.list_policies()) == 0

    def test_delete_policy_not_found(self):
        eng = _engine()
        assert eng.delete_policy("nonexistent") is False

    def test_delete_reduces_count(self):
        eng = _engine()
        p1 = eng.create_policy(name="p1", required_tags=["env"])
        eng.create_policy(name="p2", required_tags=["owner"])
        eng.delete_policy(p1.id)
        assert len(eng.list_policies()) == 1


# -------------------------------------------------------------------
# Suggest tags
# -------------------------------------------------------------------


class TestSuggestTags:
    def test_suggest_prod_environment(self):
        eng = _engine()
        s = eng.suggest_tags("my-prod-server", "ec2")
        assert s.get("environment") == "production"

    def test_suggest_staging_environment(self):
        eng = _engine()
        s = eng.suggest_tags("my-staging-app", "ec2")
        assert s.get("environment") == "staging"

    def test_suggest_stg_environment(self):
        eng = _engine()
        s = eng.suggest_tags("api-stg-01", "ec2")
        assert s.get("environment") == "staging"

    def test_suggest_dev_environment(self):
        eng = _engine()
        s = eng.suggest_tags("dev-worker", "ec2")
        assert s.get("environment") == "development"

    def test_suggest_data_tier_for_database(self):
        eng = _engine()
        s = eng.suggest_tags("r-1", "rds-database")
        assert s.get("tier") == "data"

    def test_suggest_network_tier_for_lb(self):
        eng = _engine()
        s = eng.suggest_tags("r-1", "elb-balancer")
        assert s.get("tier") == "network"

    def test_suggest_compute_tier_for_instance(self):
        eng = _engine()
        s = eng.suggest_tags("r-1", "ec2-instance")
        assert s.get("tier") == "compute"

    def test_suggest_storage_tier_for_bucket(self):
        eng = _engine()
        s = eng.suggest_tags("r-1", "s3-bucket")
        assert s.get("tier") == "storage"

    def test_suggest_owner_from_existing_records(self):
        eng, _ = _engine_with_policy(required=["owner"])
        eng.scan_resource(
            "i-1",
            "ec2",
            ResourceProvider.AWS,
            {"owner": "platform-team"},
        )
        s = eng.suggest_tags("i-2", "ec2")
        assert s.get("owner") == "platform-team"

    def test_suggest_no_match_returns_empty(self):
        eng = _engine()
        s = eng.suggest_tags("xyz-123", "custom-type")
        assert s == {}


# -------------------------------------------------------------------
# Stats
# -------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        eng = _engine()
        s = eng.get_stats()
        assert s["total_policies"] == 0
        assert s["total_records"] == 0
        assert s["compliant_records"] == 0
        assert s["non_compliant_records"] == 0

    def test_stats_with_data(self):
        eng, _ = _engine_with_policy(required=["env"])
        eng.scan_resource(
            "r1",
            "ec2",
            ResourceProvider.AWS,
            {"env": "prod"},
        )
        eng.scan_resource(
            "r2",
            "ec2",
            ResourceProvider.AWS,
            {},
        )
        s = eng.get_stats()
        assert s["total_policies"] == 1
        assert s["total_records"] == 2
        assert s["compliant_records"] == 1
        assert s["non_compliant_records"] == 1

    def test_stats_non_compliant_includes_partial(self):
        eng, _ = _engine_with_policy(required=["env", "owner"])
        eng.scan_resource(
            "r1",
            "ec2",
            ResourceProvider.AWS,
            {"env": "prod"},
        )
        s = eng.get_stats()
        # PARTIALLY_COMPLIANT counts as non_compliant in stats
        assert s["non_compliant_records"] == 1
