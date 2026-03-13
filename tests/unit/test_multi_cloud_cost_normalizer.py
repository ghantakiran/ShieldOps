"""Tests for MultiCloudCostNormalizer."""

from __future__ import annotations

from shieldops.billing.multi_cloud_cost_normalizer import (
    CloudProvider,
    CostCategory,
    MultiCloudCostNormalizer,
    NormalizationStatus,
)


def _engine(**kw) -> MultiCloudCostNormalizer:
    return MultiCloudCostNormalizer(**kw)


class TestEnums:
    def test_cloud_provider_values(self):
        for v in CloudProvider:
            assert isinstance(v.value, str)

    def test_cost_category_values(self):
        for v in CostCategory:
            assert isinstance(v.value, str)

    def test_normalization_status_values(self):
        for v in NormalizationStatus:
            assert isinstance(v.value, str)


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(account_id="a1")
        assert r.account_id == "a1"

    def test_eviction(self):
        eng = _engine(max_records=5)
        for i in range(8):
            eng.add_record(account_id=f"a-{i}")
        assert len(eng._records) == 5


class TestProcess:
    def test_found(self):
        eng = _engine()
        r = eng.add_record(
            account_id="a1",
            raw_cost=1000,
            normalized_cost=950,
        )
        a = eng.process(r.id)
        assert a.variance_pct == 5.0

    def test_missing(self):
        result = _engine().process("x")
        assert result["status"] == "not_found"

    def test_zero_raw(self):
        eng = _engine()
        r = eng.add_record(raw_cost=0)
        a = eng.process(r.id)
        assert a.variance_pct == 0.0


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(normalized_cost=500)
        rpt = eng.generate_report()
        assert rpt.total_normalized_cost == 500.0

    def test_empty(self):
        assert _engine().generate_report().total_records == 0

    def test_unmapped_recommendation(self):
        eng = _engine()
        eng.add_record(
            normalization_status=NormalizationStatus.UNMAPPED,
        )
        rpt = eng.generate_report()
        assert any("unmapped" in r for r in rpt.recommendations)


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(account_id="a1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestNormalizeBillingTaxonomy:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            cloud_provider=CloudProvider.AWS,
            raw_cost=100,
            normalized_cost=95,
        )
        result = eng.normalize_billing_taxonomy()
        assert len(result) == 1
        assert result[0]["provider"] == "aws"

    def test_empty(self):
        assert _engine().normalize_billing_taxonomy() == []


class TestReconcileCrossCloudSpend:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(
            cloud_provider=CloudProvider.AWS,
            cost_category=CostCategory.COMPUTE,
            normalized_cost=500,
        )
        eng.add_record(
            cloud_provider=CloudProvider.GCP,
            cost_category=CostCategory.COMPUTE,
            normalized_cost=300,
        )
        result = eng.reconcile_cross_cloud_spend()
        assert len(result) == 1
        assert result[0]["total"] == 800.0

    def test_empty(self):
        assert _engine().reconcile_cross_cloud_spend() == []


class TestGenerateUnifiedCostView:
    def test_with_data(self):
        eng = _engine()
        eng.add_record(account_id="a1", normalized_cost=1000)
        result = eng.generate_unified_cost_view()
        assert result[0]["total_cost"] == 1000.0

    def test_empty(self):
        assert _engine().generate_unified_cost_view() == []
