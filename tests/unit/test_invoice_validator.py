"""Tests for shieldops.billing.invoice_validator — InvoiceValidationEngine."""

from __future__ import annotations

from shieldops.billing.invoice_validator import (
    DiscrepancyDetail,
    DiscrepancyType,
    InvoiceCategory,
    InvoiceRecord,
    InvoiceValidationEngine,
    InvoiceValidationReport,
    ValidationStatus,
)


def _engine(**kw) -> InvoiceValidationEngine:
    return InvoiceValidationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_discrepancy_overcharge(self):
        assert DiscrepancyType.OVERCHARGE == "overcharge"

    def test_discrepancy_undercharge(self):
        assert DiscrepancyType.UNDERCHARGE == "undercharge"

    def test_discrepancy_missing_item(self):
        assert DiscrepancyType.MISSING_ITEM == "missing_item"

    def test_discrepancy_duplicate_charge(self):
        assert DiscrepancyType.DUPLICATE_CHARGE == "duplicate_charge"

    def test_discrepancy_rate_mismatch(self):
        assert DiscrepancyType.RATE_MISMATCH == "rate_mismatch"

    def test_status_validated(self):
        assert ValidationStatus.VALIDATED == "validated"

    def test_status_discrepancy_found(self):
        assert ValidationStatus.DISCREPANCY_FOUND == "discrepancy_found"

    def test_status_pending_review(self):
        assert ValidationStatus.PENDING_REVIEW == "pending_review"

    def test_status_disputed(self):
        assert ValidationStatus.DISPUTED == "disputed"

    def test_status_resolved(self):
        assert ValidationStatus.RESOLVED == "resolved"

    def test_category_compute(self):
        assert InvoiceCategory.COMPUTE == "compute"

    def test_category_storage(self):
        assert InvoiceCategory.STORAGE == "storage"

    def test_category_network(self):
        assert InvoiceCategory.NETWORK == "network"

    def test_category_database(self):
        assert InvoiceCategory.DATABASE == "database"

    def test_category_support(self):
        assert InvoiceCategory.SUPPORT == "support"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_invoice_record_defaults(self):
        r = InvoiceRecord()
        assert r.id
        assert r.invoice_id == ""
        assert r.discrepancy_type == DiscrepancyType.OVERCHARGE
        assert r.validation_status == ValidationStatus.PENDING_REVIEW
        assert r.invoice_category == InvoiceCategory.COMPUTE
        assert r.discrepancy_amount == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_discrepancy_detail_defaults(self):
        d = DiscrepancyDetail()
        assert d.id
        assert d.detail_name == ""
        assert d.discrepancy_type == DiscrepancyType.OVERCHARGE
        assert d.amount_threshold == 0.0
        assert d.avg_discrepancy_amount == 0.0
        assert d.description == ""
        assert d.created_at > 0

    def test_invoice_validation_report_defaults(self):
        r = InvoiceValidationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_discrepancies == 0
        assert r.high_discrepancies == 0
        assert r.avg_discrepancy_amount == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_category == {}
        assert r.top_items == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_invoice
# ---------------------------------------------------------------------------


class TestRecordInvoice:
    def test_basic(self):
        eng = _engine()
        r = eng.record_invoice(
            invoice_id="INV-001",
            discrepancy_type=DiscrepancyType.OVERCHARGE,
            validation_status=ValidationStatus.DISCREPANCY_FOUND,
            invoice_category=InvoiceCategory.COMPUTE,
            discrepancy_amount=150.0,
            team="finance",
        )
        assert r.invoice_id == "INV-001"
        assert r.discrepancy_type == DiscrepancyType.OVERCHARGE
        assert r.validation_status == ValidationStatus.DISCREPANCY_FOUND
        assert r.invoice_category == InvoiceCategory.COMPUTE
        assert r.discrepancy_amount == 150.0
        assert r.team == "finance"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_invoice(invoice_id=f"INV-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_invoice
# ---------------------------------------------------------------------------


class TestGetInvoice:
    def test_found(self):
        eng = _engine()
        r = eng.record_invoice(
            invoice_id="INV-001",
            validation_status=ValidationStatus.VALIDATED,
        )
        result = eng.get_invoice(r.id)
        assert result is not None
        assert result.validation_status == ValidationStatus.VALIDATED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_invoice("nonexistent") is None


# ---------------------------------------------------------------------------
# list_invoices
# ---------------------------------------------------------------------------


class TestListInvoices:
    def test_list_all(self):
        eng = _engine()
        eng.record_invoice(invoice_id="INV-001")
        eng.record_invoice(invoice_id="INV-002")
        assert len(eng.list_invoices()) == 2

    def test_filter_by_dtype(self):
        eng = _engine()
        eng.record_invoice(
            invoice_id="INV-001",
            discrepancy_type=DiscrepancyType.OVERCHARGE,
        )
        eng.record_invoice(
            invoice_id="INV-002",
            discrepancy_type=DiscrepancyType.UNDERCHARGE,
        )
        results = eng.list_invoices(dtype=DiscrepancyType.OVERCHARGE)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_invoice(
            invoice_id="INV-001",
            validation_status=ValidationStatus.VALIDATED,
        )
        eng.record_invoice(
            invoice_id="INV-002",
            validation_status=ValidationStatus.DISPUTED,
        )
        results = eng.list_invoices(status=ValidationStatus.VALIDATED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_invoice(invoice_id="INV-001", team="finance")
        eng.record_invoice(invoice_id="INV-002", team="operations")
        results = eng.list_invoices(team="finance")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_invoice(invoice_id=f"INV-{i}")
        assert len(eng.list_invoices(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_discrepancy
# ---------------------------------------------------------------------------


class TestAddDiscrepancy:
    def test_basic(self):
        eng = _engine()
        d = eng.add_discrepancy(
            detail_name="rate-check",
            discrepancy_type=DiscrepancyType.RATE_MISMATCH,
            amount_threshold=100.0,
            avg_discrepancy_amount=75.0,
            description="Rate mismatch check",
        )
        assert d.detail_name == "rate-check"
        assert d.discrepancy_type == DiscrepancyType.RATE_MISMATCH
        assert d.amount_threshold == 100.0
        assert d.avg_discrepancy_amount == 75.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_discrepancy(detail_name=f"det-{i}")
        assert len(eng._discrepancies) == 2


# ---------------------------------------------------------------------------
# analyze_discrepancy_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeDiscrepancyPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_invoice(
            invoice_id="INV-001",
            discrepancy_type=DiscrepancyType.OVERCHARGE,
            discrepancy_amount=100.0,
        )
        eng.record_invoice(
            invoice_id="INV-002",
            discrepancy_type=DiscrepancyType.OVERCHARGE,
            discrepancy_amount=200.0,
        )
        result = eng.analyze_discrepancy_patterns()
        assert "overcharge" in result
        assert result["overcharge"]["count"] == 2
        assert result["overcharge"]["avg_discrepancy_amount"] == 150.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_discrepancy_patterns() == {}


# ---------------------------------------------------------------------------
# identify_high_discrepancies
# ---------------------------------------------------------------------------


class TestIdentifyHighDiscrepancies:
    def test_detects_discrepancy_found(self):
        eng = _engine()
        eng.record_invoice(
            invoice_id="INV-001",
            validation_status=ValidationStatus.DISCREPANCY_FOUND,
            discrepancy_amount=500.0,
        )
        eng.record_invoice(
            invoice_id="INV-002",
            validation_status=ValidationStatus.VALIDATED,
        )
        results = eng.identify_high_discrepancies()
        assert len(results) == 1
        assert results[0]["invoice_id"] == "INV-001"

    def test_detects_disputed(self):
        eng = _engine()
        eng.record_invoice(
            invoice_id="INV-001",
            validation_status=ValidationStatus.DISPUTED,
        )
        results = eng.identify_high_discrepancies()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_discrepancies() == []


# ---------------------------------------------------------------------------
# rank_by_discrepancy_amount
# ---------------------------------------------------------------------------


class TestRankByDiscrepancyAmount:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_invoice(invoice_id="INV-001", team="finance", discrepancy_amount=300.0)
        eng.record_invoice(invoice_id="INV-002", team="finance", discrepancy_amount=200.0)
        eng.record_invoice(invoice_id="INV-003", team="operations", discrepancy_amount=100.0)
        results = eng.rank_by_discrepancy_amount()
        assert len(results) == 2
        assert results[0]["team"] == "finance"
        assert results[0]["avg_discrepancy_amount"] == 250.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_discrepancy_amount() == []


# ---------------------------------------------------------------------------
# detect_billing_anomalies
# ---------------------------------------------------------------------------


class TestDetectBillingAnomalies:
    def test_stable(self):
        eng = _engine()
        for a in [100.0, 100.0, 100.0, 100.0]:
            eng.add_discrepancy(detail_name="d", avg_discrepancy_amount=a)
        result = eng.detect_billing_anomalies()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for a in [50.0, 50.0, 200.0, 200.0]:
            eng.add_discrepancy(detail_name="d", avg_discrepancy_amount=a)
        result = eng.detect_billing_anomalies()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_billing_anomalies()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_invoice(
            invoice_id="INV-001",
            discrepancy_type=DiscrepancyType.OVERCHARGE,
            validation_status=ValidationStatus.DISCREPANCY_FOUND,
            discrepancy_amount=500.0,
            team="finance",
        )
        report = eng.generate_report()
        assert isinstance(report, InvoiceValidationReport)
        assert report.total_records == 1
        assert report.high_discrepancies == 1
        assert report.avg_discrepancy_amount == 500.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_invoice(invoice_id="INV-001")
        eng.add_discrepancy(detail_name="d1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._discrepancies) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_discrepancies"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_invoice(
            invoice_id="INV-001",
            discrepancy_type=DiscrepancyType.OVERCHARGE,
            team="finance",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_invoices"] == 1
        assert "overcharge" in stats["type_distribution"]
