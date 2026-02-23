"""Tests for shieldops.analytics.cost_normalizer -- CostNormalizer."""

from __future__ import annotations

import pytest

from shieldops.analytics.cost_normalizer import (
    CloudProvider,
    CostComparison,
    CostNormalizer,
    NormalizationResult,
    PricingEntry,
    ResourceCategory,
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _normalizer(**kwargs) -> CostNormalizer:
    return CostNormalizer(**kwargs)


def _normalizer_with_pricing() -> CostNormalizer:
    """Return a normalizer pre-loaded with compute pricing for 3 providers."""
    n = _normalizer()
    n.add_pricing(
        CloudProvider.AWS,
        ResourceCategory.COMPUTE,
        "m5.large",
        0.096,
        region="us-east-1",
    )
    n.add_pricing(
        CloudProvider.GCP,
        ResourceCategory.COMPUTE,
        "m5.large",
        0.084,
        region="us-east-1",
    )
    n.add_pricing(
        CloudProvider.AZURE,
        ResourceCategory.COMPUTE,
        "m5.large",
        0.100,
        region="us-east-1",
    )
    return n


# -------------------------------------------------------------------
# Enum values
# -------------------------------------------------------------------


class TestEnums:
    def test_cloud_provider_aws(self):
        assert CloudProvider.AWS == "aws"

    def test_cloud_provider_gcp(self):
        assert CloudProvider.GCP == "gcp"

    def test_cloud_provider_azure(self):
        assert CloudProvider.AZURE == "azure"

    def test_resource_category_compute(self):
        assert ResourceCategory.COMPUTE == "compute"

    def test_resource_category_storage(self):
        assert ResourceCategory.STORAGE == "storage"

    def test_resource_category_network(self):
        assert ResourceCategory.NETWORK == "network"

    def test_resource_category_database(self):
        assert ResourceCategory.DATABASE == "database"

    def test_resource_category_serverless(self):
        assert ResourceCategory.SERVERLESS == "serverless"

    def test_resource_category_container(self):
        assert ResourceCategory.CONTAINER == "container"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_pricing_entry_defaults(self):
        e = PricingEntry(
            provider=CloudProvider.AWS,
            category=ResourceCategory.COMPUTE,
            resource_type="m5.large",
            price_per_unit=0.096,
        )
        assert e.id
        assert e.unit == "hour"
        assert e.region == "us-east-1"
        assert e.metadata == {}
        assert e.updated_at > 0

    def test_cost_comparison_defaults(self):
        c = CostComparison(
            resource_type="m5.large",
            category=ResourceCategory.COMPUTE,
        )
        assert c.providers == {}
        assert c.cheapest == ""
        assert c.savings_pct == 0.0

    def test_normalization_result_defaults(self):
        r = NormalizationResult(workload_name="web")
        assert r.id
        assert r.comparisons == []
        assert r.total_by_provider == {}
        assert r.recommended_provider == ""
        assert r.monthly_savings == 0.0
        assert r.analyzed_at > 0


# -------------------------------------------------------------------
# Add pricing
# -------------------------------------------------------------------


class TestAddPricing:
    def test_add_basic(self):
        n = _normalizer()
        e = n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "m5.large",
            0.096,
        )
        assert e.provider == CloudProvider.AWS
        assert e.resource_type == "m5.large"
        assert e.price_per_unit == 0.096

    def test_add_with_metadata(self):
        n = _normalizer()
        e = n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "m5.large",
            0.096,
            metadata={"vcpus": 2, "memory_gb": 8},
        )
        assert e.metadata["vcpus"] == 2

    def test_add_custom_unit_and_region(self):
        n = _normalizer()
        e = n.add_pricing(
            CloudProvider.GCP,
            ResourceCategory.STORAGE,
            "standard",
            0.023,
            unit="gb-month",
            region="us-west-1",
        )
        assert e.unit == "gb-month"
        assert e.region == "us-west-1"

    def test_add_multiple_entries(self):
        n = _normalizer()
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "m5.large",
            0.096,
        )
        n.add_pricing(
            CloudProvider.GCP,
            ResourceCategory.COMPUTE,
            "n1-standard-2",
            0.084,
        )
        assert len(n.get_pricing()) == 2

    def test_add_exceeds_limit(self):
        n = _normalizer(max_pricing_entries=2)
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "t1",
            0.05,
        )
        n.add_pricing(
            CloudProvider.GCP,
            ResourceCategory.COMPUTE,
            "t2",
            0.04,
        )
        with pytest.raises(
            ValueError,
            match="Maximum pricing entries limit",
        ):
            n.add_pricing(
                CloudProvider.AZURE,
                ResourceCategory.COMPUTE,
                "t3",
                0.06,
            )


# -------------------------------------------------------------------
# Compare resource
# -------------------------------------------------------------------


class TestCompareResource:
    def test_compare_finds_cheapest(self):
        n = _normalizer_with_pricing()
        cmp = n.compare_resource(
            "m5.large",
            ResourceCategory.COMPUTE,
        )
        assert cmp.cheapest == CloudProvider.GCP
        assert len(cmp.providers) == 3

    def test_compare_savings_pct(self):
        n = _normalizer_with_pricing()
        cmp = n.compare_resource(
            "m5.large",
            ResourceCategory.COMPUTE,
        )
        # most_expensive=0.100, cheapest=0.084
        # savings = (0.100-0.084)/0.100 * 100 = 16.0
        assert cmp.savings_pct == pytest.approx(16.0, abs=0.01)

    def test_compare_single_provider(self):
        n = _normalizer()
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "t3.micro",
            0.010,
        )
        cmp = n.compare_resource(
            "t3.micro",
            ResourceCategory.COMPUTE,
        )
        assert cmp.cheapest == CloudProvider.AWS
        assert cmp.savings_pct == 0.0

    def test_compare_no_entries(self):
        n = _normalizer()
        cmp = n.compare_resource(
            "nonexistent",
            ResourceCategory.COMPUTE,
        )
        assert cmp.cheapest == ""
        assert cmp.providers == {}
        assert cmp.savings_pct == 0.0

    def test_compare_category_filter(self):
        n = _normalizer()
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "m5.large",
            0.096,
        )
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.STORAGE,
            "m5.large",
            0.023,
        )
        cmp = n.compare_resource(
            "m5.large",
            ResourceCategory.STORAGE,
        )
        assert len(cmp.providers) == 1
        assert cmp.providers[CloudProvider.AWS] == 0.023


# -------------------------------------------------------------------
# Analyze workload
# -------------------------------------------------------------------


class TestAnalyzeWorkload:
    def test_basic_workload(self):
        n = _normalizer_with_pricing()
        result = n.analyze_workload(
            "web-app",
            [{"resource_type": "m5.large", "category": "compute", "quantity": 2, "hours": 730}],
        )
        assert result.workload_name == "web-app"
        assert result.recommended_provider == CloudProvider.GCP
        assert len(result.comparisons) == 1

    def test_workload_monthly_savings(self):
        n = _normalizer_with_pricing()
        result = n.analyze_workload(
            "api",
            [{"resource_type": "m5.large", "category": "compute", "quantity": 1, "hours": 730}],
        )
        # AWS=0.096*730=70.08, GCP=0.084*730=61.32, Azure=0.1*730=73
        # savings = 73.0 - 61.32 = 11.68
        assert result.monthly_savings == pytest.approx(11.68, abs=0.01)

    def test_workload_multiple_resources(self):
        n = _normalizer()
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "m5.large",
            0.096,
        )
        n.add_pricing(
            CloudProvider.GCP,
            ResourceCategory.COMPUTE,
            "m5.large",
            0.084,
        )
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.DATABASE,
            "db.r5.large",
            0.250,
        )
        n.add_pricing(
            CloudProvider.GCP,
            ResourceCategory.DATABASE,
            "db.r5.large",
            0.230,
        )
        result = n.analyze_workload(
            "fullstack",
            [
                {"resource_type": "m5.large", "category": "compute", "quantity": 2, "hours": 730},
                {
                    "resource_type": "db.r5.large",
                    "category": "database",
                    "quantity": 1,
                    "hours": 730,
                },
            ],
        )
        assert result.recommended_provider == CloudProvider.GCP
        assert len(result.total_by_provider) == 2

    def test_workload_empty_resources(self):
        n = _normalizer()
        result = n.analyze_workload("empty", [])
        assert result.recommended_provider == ""
        assert result.monthly_savings == 0.0
        assert result.comparisons == []

    def test_workload_default_hours(self):
        n = _normalizer()
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "t3.nano",
            0.005,
        )
        result = n.analyze_workload(
            "tiny",
            [{"resource_type": "t3.nano", "category": "compute"}],
        )
        # default quantity=1, hours=730
        expected = 0.005 * 1 * 730
        assert result.total_by_provider[CloudProvider.AWS] == (pytest.approx(expected, abs=0.01))


# -------------------------------------------------------------------
# Get pricing
# -------------------------------------------------------------------


class TestGetPricing:
    def test_get_all(self):
        n = _normalizer_with_pricing()
        assert len(n.get_pricing()) == 3

    def test_filter_by_provider(self):
        n = _normalizer_with_pricing()
        aws = n.get_pricing(provider=CloudProvider.AWS)
        assert len(aws) == 1
        assert aws[0].provider == CloudProvider.AWS

    def test_filter_by_category(self):
        n = _normalizer()
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "m5.large",
            0.096,
        )
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.STORAGE,
            "s3-standard",
            0.023,
        )
        storage = n.get_pricing(category=ResourceCategory.STORAGE)
        assert len(storage) == 1
        assert storage[0].resource_type == "s3-standard"

    def test_filter_by_both(self):
        n = _normalizer_with_pricing()
        result = n.get_pricing(
            provider=CloudProvider.GCP,
            category=ResourceCategory.COMPUTE,
        )
        assert len(result) == 1

    def test_get_pricing_empty(self):
        n = _normalizer()
        assert n.get_pricing() == []


# -------------------------------------------------------------------
# Update pricing
# -------------------------------------------------------------------


class TestUpdatePricing:
    def test_update_success(self):
        n = _normalizer()
        e = n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "m5.large",
            0.096,
        )
        updated = n.update_pricing(e.id, 0.090)
        assert updated is not None
        assert updated.price_per_unit == 0.090

    def test_update_not_found(self):
        n = _normalizer()
        assert n.update_pricing("nonexistent", 0.05) is None

    def test_update_changes_timestamp(self):
        n = _normalizer()
        e = n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "m5.large",
            0.096,
        )
        original_ts = e.updated_at
        updated = n.update_pricing(e.id, 0.090)
        assert updated is not None
        assert updated.updated_at >= original_ts


# -------------------------------------------------------------------
# Delete pricing
# -------------------------------------------------------------------


class TestDeletePricing:
    def test_delete_success(self):
        n = _normalizer()
        e = n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "m5.large",
            0.096,
        )
        assert n.delete_pricing(e.id) is True
        assert len(n.get_pricing()) == 0

    def test_delete_not_found(self):
        n = _normalizer()
        assert n.delete_pricing("nonexistent") is False

    def test_delete_reduces_count(self):
        n = _normalizer()
        e1 = n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "m5.large",
            0.096,
        )
        n.add_pricing(
            CloudProvider.GCP,
            ResourceCategory.COMPUTE,
            "n1-standard-2",
            0.084,
        )
        n.delete_pricing(e1.id)
        assert len(n.get_pricing()) == 1


# -------------------------------------------------------------------
# Get cheapest provider
# -------------------------------------------------------------------


class TestGetCheapestProvider:
    def test_cheapest_across_providers(self):
        n = _normalizer_with_pricing()
        result = n.get_cheapest_provider(ResourceCategory.COMPUTE)
        assert result["cheapest_provider"] == CloudProvider.GCP
        assert result["category"] == ResourceCategory.COMPUTE

    def test_cheapest_no_entries(self):
        n = _normalizer()
        result = n.get_cheapest_provider(ResourceCategory.STORAGE)
        assert result["cheapest_provider"] == ""
        assert result["avg_price"] == 0.0

    def test_cheapest_includes_all_providers(self):
        n = _normalizer_with_pricing()
        result = n.get_cheapest_provider(ResourceCategory.COMPUTE)
        assert "all_providers" in result
        assert len(result["all_providers"]) == 3

    def test_cheapest_avg_price_multiple_entries(self):
        n = _normalizer()
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "t1",
            0.10,
        )
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "t2",
            0.20,
        )
        result = n.get_cheapest_provider(ResourceCategory.COMPUTE)
        # avg = (0.10 + 0.20) / 2 = 0.15
        assert result["avg_price"] == pytest.approx(0.15, abs=0.001)


# -------------------------------------------------------------------
# Stats
# -------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        n = _normalizer()
        s = n.get_stats()
        assert s["total_pricing_entries"] == 0
        assert s["providers"] == 0
        assert s["categories"] == 0

    def test_stats_with_data(self):
        n = _normalizer_with_pricing()
        s = n.get_stats()
        assert s["total_pricing_entries"] == 3
        assert s["providers"] == 3
        assert s["categories"] == 1

    def test_stats_multiple_categories(self):
        n = _normalizer()
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.COMPUTE,
            "m5.large",
            0.096,
        )
        n.add_pricing(
            CloudProvider.AWS,
            ResourceCategory.STORAGE,
            "s3",
            0.023,
        )
        s = n.get_stats()
        assert s["categories"] == 2
        assert s["providers"] == 1
