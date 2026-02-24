"""Tests for shieldops.billing.billing_reconciler — CloudBillingReconciler."""

from __future__ import annotations

from shieldops.billing.billing_reconciler import (
    BillingProvider,
    BillingRecord,
    CloudBillingReconciler,
    DiscrepancyType,
    ReconcilerReport,
    ReconciliationResult,
    ReconciliationStatus,
)


def _engine(**kw) -> CloudBillingReconciler:
    return CloudBillingReconciler(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DiscrepancyType (5 values)

    def test_discrepancy_type_overcharge(self):
        assert DiscrepancyType.OVERCHARGE == "overcharge"

    def test_discrepancy_type_undercharge(self):
        assert DiscrepancyType.UNDERCHARGE == "undercharge"

    def test_discrepancy_type_unexpected_service(self):
        assert DiscrepancyType.UNEXPECTED_SERVICE == "unexpected_service"

    def test_discrepancy_type_missing_discount(self):
        assert DiscrepancyType.MISSING_DISCOUNT == "missing_discount"

    def test_discrepancy_type_pricing_change(self):
        assert DiscrepancyType.PRICING_CHANGE == "pricing_change"

    # ReconciliationStatus (5 values)

    def test_reconciliation_status_matched(self):
        assert ReconciliationStatus.MATCHED == "matched"

    def test_reconciliation_status_discrepancy_found(self):
        assert ReconciliationStatus.DISCREPANCY_FOUND == "discrepancy_found"

    def test_reconciliation_status_pending_review(self):
        assert ReconciliationStatus.PENDING_REVIEW == "pending_review"

    def test_reconciliation_status_disputed(self):
        assert ReconciliationStatus.DISPUTED == "disputed"

    def test_reconciliation_status_resolved(self):
        assert ReconciliationStatus.RESOLVED == "resolved"

    # BillingProvider (5 values)

    def test_billing_provider_aws(self):
        assert BillingProvider.AWS == "aws"

    def test_billing_provider_gcp(self):
        assert BillingProvider.GCP == "gcp"

    def test_billing_provider_azure(self):
        assert BillingProvider.AZURE == "azure"

    def test_billing_provider_on_prem(self):
        assert BillingProvider.ON_PREM == "on_prem"

    def test_billing_provider_hybrid(self):
        assert BillingProvider.HYBRID == "hybrid"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_billing_record_defaults(self):
        rec = BillingRecord()
        assert rec.id
        assert rec.provider == BillingProvider.AWS
        assert rec.account_id == ""
        assert rec.service_name == ""
        assert rec.expected_cost == 0.0
        assert rec.actual_cost == 0.0
        assert rec.discrepancy == 0.0
        assert rec.discrepancy_type is None
        assert rec.status == ReconciliationStatus.PENDING_REVIEW
        assert rec.billing_period == ""
        assert rec.created_at > 0

    def test_reconciliation_result_defaults(self):
        result = ReconciliationResult()
        assert result.id
        assert result.billing_period == ""
        assert result.total_expected == 0.0
        assert result.total_actual == 0.0
        assert result.total_discrepancy == 0.0
        assert result.discrepancy_count == 0
        assert result.status == ReconciliationStatus.PENDING_REVIEW
        assert result.created_at > 0

    def test_reconciler_report_defaults(self):
        report = ReconcilerReport()
        assert report.total_records == 0
        assert report.total_reconciliations == 0
        assert report.total_discrepancy_amount == 0.0
        assert report.by_provider == {}
        assert report.by_type == {}
        assert report.by_status == {}
        assert report.top_discrepancies == []
        assert report.recommendations == []
        assert report.generated_at > 0


# -------------------------------------------------------------------
# record_billing
# -------------------------------------------------------------------


class TestRecordBilling:
    def test_basic_record(self):
        eng = _engine()
        rec = eng.record_billing(
            provider=BillingProvider.AWS,
            service_name="ec2",
            expected_cost=100.0,
            actual_cost=100.0,
        )
        assert rec.service_name == "ec2"
        assert rec.discrepancy == 0.0
        assert len(eng.list_records()) == 1

    def test_record_assigns_unique_ids(self):
        eng = _engine()
        r1 = eng.record_billing(service_name="s3")
        r2 = eng.record_billing(service_name="rds")
        assert r1.id != r2.id

    def test_overcharge_detected(self):
        eng = _engine()
        rec = eng.record_billing(
            expected_cost=100.0,
            actual_cost=120.0,
        )
        assert rec.discrepancy == 20.0
        assert rec.discrepancy_type == DiscrepancyType.OVERCHARGE

    def test_undercharge_detected(self):
        eng = _engine()
        rec = eng.record_billing(
            expected_cost=100.0,
            actual_cost=80.0,
        )
        assert rec.discrepancy == -20.0
        assert rec.discrepancy_type == DiscrepancyType.UNDERCHARGE

    def test_within_threshold_matched(self):
        eng = _engine(discrepancy_threshold_pct=10.0)
        rec = eng.record_billing(
            expected_cost=100.0,
            actual_cost=105.0,
        )
        assert rec.discrepancy_type is None
        assert rec.status == ReconciliationStatus.MATCHED

    def test_eviction_at_max_records(self):
        eng = _engine(max_records=3)
        ids = []
        for i in range(4):
            rec = eng.record_billing(
                service_name=f"svc-{i}",
            )
            ids.append(rec.id)
        records = eng.list_records(limit=100)
        assert len(records) == 3
        found = {r.id for r in records}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_record
# -------------------------------------------------------------------


class TestGetRecord:
    def test_get_existing(self):
        eng = _engine()
        rec = eng.record_billing(service_name="ec2")
        found = eng.get_record(rec.id)
        assert found is not None
        assert found.id == rec.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# -------------------------------------------------------------------
# list_records
# -------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_billing(service_name="a")
        eng.record_billing(service_name="b")
        eng.record_billing(service_name="c")
        assert len(eng.list_records()) == 3

    def test_filter_by_provider(self):
        eng = _engine()
        eng.record_billing(provider=BillingProvider.AWS)
        eng.record_billing(provider=BillingProvider.GCP)
        eng.record_billing(provider=BillingProvider.AWS)
        results = eng.list_records(
            provider=BillingProvider.AWS,
        )
        assert len(results) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_billing(
            expected_cost=100.0,
            actual_cost=100.0,
        )
        eng.record_billing(
            expected_cost=100.0,
            actual_cost=200.0,
        )
        matched = eng.list_records(
            status=ReconciliationStatus.MATCHED,
        )
        assert len(matched) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_billing(
                service_name=f"svc-{i}",
            )
        results = eng.list_records(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# reconcile_period
# -------------------------------------------------------------------


class TestReconcilePeriod:
    def test_clean_period(self):
        eng = _engine()
        eng.record_billing(
            expected_cost=100.0,
            actual_cost=100.0,
            billing_period="2026-01",
        )
        result = eng.reconcile_period("2026-01")
        assert result.total_expected == 100.0
        assert result.total_actual == 100.0
        assert result.discrepancy_count == 0
        assert result.status == ReconciliationStatus.MATCHED

    def test_period_with_discrepancy(self):
        eng = _engine()
        eng.record_billing(
            expected_cost=100.0,
            actual_cost=200.0,
            billing_period="2026-01",
        )
        result = eng.reconcile_period("2026-01")
        assert result.total_discrepancy == 100.0
        assert result.discrepancy_count == 1
        assert result.status == ReconciliationStatus.DISCREPANCY_FOUND

    def test_empty_period(self):
        eng = _engine()
        result = eng.reconcile_period("2099-01")
        assert result.total_expected == 0.0
        assert result.discrepancy_count == 0


# -------------------------------------------------------------------
# detect_discrepancies
# -------------------------------------------------------------------


class TestDetectDiscrepancies:
    def test_finds_discrepancies(self):
        eng = _engine()
        eng.record_billing(
            expected_cost=100.0,
            actual_cost=200.0,
        )
        eng.record_billing(
            expected_cost=100.0,
            actual_cost=100.0,
        )
        discs = eng.detect_discrepancies()
        assert len(discs) == 1

    def test_no_discrepancies(self):
        eng = _engine()
        eng.record_billing(
            expected_cost=100.0,
            actual_cost=100.0,
        )
        discs = eng.detect_discrepancies()
        assert len(discs) == 0


# -------------------------------------------------------------------
# flag_unexpected_charges
# -------------------------------------------------------------------


class TestFlagUnexpectedCharges:
    def test_flags_unexpected(self):
        eng = _engine()
        eng.record_billing(
            expected_cost=0.0,
            actual_cost=50.0,
        )
        unexpected = eng.flag_unexpected_charges()
        assert len(unexpected) == 1
        assert unexpected[0].discrepancy_type == DiscrepancyType.UNEXPECTED_SERVICE

    def test_no_unexpected(self):
        eng = _engine()
        eng.record_billing(
            expected_cost=100.0,
            actual_cost=100.0,
        )
        unexpected = eng.flag_unexpected_charges()
        assert len(unexpected) == 0


# -------------------------------------------------------------------
# calculate_accuracy_rate
# -------------------------------------------------------------------


class TestCalculateAccuracyRate:
    def test_perfect_accuracy(self):
        eng = _engine()
        eng.record_billing(
            expected_cost=100.0,
            actual_cost=100.0,
        )
        rate = eng.calculate_accuracy_rate()
        assert rate == 100.0

    def test_partial_accuracy(self):
        eng = _engine()
        eng.record_billing(
            expected_cost=100.0,
            actual_cost=100.0,
        )
        eng.record_billing(
            expected_cost=100.0,
            actual_cost=200.0,
        )
        rate = eng.calculate_accuracy_rate()
        assert rate == 50.0

    def test_empty_accuracy(self):
        eng = _engine()
        rate = eng.calculate_accuracy_rate()
        assert rate == 100.0


# -------------------------------------------------------------------
# estimate_annual_leakage
# -------------------------------------------------------------------


class TestEstimateAnnualLeakage:
    def test_estimates_leakage(self):
        eng = _engine()
        eng.record_billing(
            expected_cost=100.0,
            actual_cost=200.0,
        )
        leakage = eng.estimate_annual_leakage()
        assert leakage == 1200.0

    def test_no_leakage(self):
        eng = _engine()
        leakage = eng.estimate_annual_leakage()
        assert leakage == 0.0


# -------------------------------------------------------------------
# generate_reconciler_report
# -------------------------------------------------------------------


class TestGenerateReconcilerReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_billing(
            provider=BillingProvider.AWS,
            expected_cost=100.0,
            actual_cost=200.0,
        )
        eng.record_billing(
            provider=BillingProvider.GCP,
            expected_cost=50.0,
            actual_cost=50.0,
        )
        report = eng.generate_reconciler_report()
        assert report.total_records == 2
        assert report.total_discrepancy_amount > 0
        assert isinstance(report.by_provider, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_reconciler_report()
        assert report.total_records == 0
        assert report.total_discrepancy_amount == 0.0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_billing(service_name="a")
        eng.record_billing(service_name="b")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_records()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_reconciliations"] == 0
        assert stats["discrepancy_threshold_pct"] == 5.0
        assert stats["accuracy_rate"] == 100.0
        assert stats["provider_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.record_billing(
            provider=BillingProvider.AWS,
            expected_cost=100.0,
            actual_cost=100.0,
        )
        eng.record_billing(
            provider=BillingProvider.GCP,
            expected_cost=50.0,
            actual_cost=50.0,
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert len(stats["provider_distribution"]) == 2
