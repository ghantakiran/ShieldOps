"""Cloud Billing Reconciler — reconcile cloud billing against expected costs."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DiscrepancyType(StrEnum):
    OVERCHARGE = "overcharge"
    UNDERCHARGE = "undercharge"
    UNEXPECTED_SERVICE = "unexpected_service"
    MISSING_DISCOUNT = "missing_discount"
    PRICING_CHANGE = "pricing_change"


class ReconciliationStatus(StrEnum):
    MATCHED = "matched"
    DISCREPANCY_FOUND = "discrepancy_found"
    PENDING_REVIEW = "pending_review"
    DISPUTED = "disputed"
    RESOLVED = "resolved"


class BillingProvider(StrEnum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    ON_PREM = "on_prem"
    HYBRID = "hybrid"


# --- Models ---


class BillingRecord(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    provider: BillingProvider = BillingProvider.AWS
    account_id: str = ""
    service_name: str = ""
    expected_cost: float = 0.0
    actual_cost: float = 0.0
    discrepancy: float = 0.0
    discrepancy_type: DiscrepancyType | None = None
    status: ReconciliationStatus = ReconciliationStatus.PENDING_REVIEW
    billing_period: str = ""
    created_at: float = Field(
        default_factory=time.time,
    )


class ReconciliationResult(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    billing_period: str = ""
    total_expected: float = 0.0
    total_actual: float = 0.0
    total_discrepancy: float = 0.0
    discrepancy_count: int = 0
    status: ReconciliationStatus = ReconciliationStatus.PENDING_REVIEW
    created_at: float = Field(
        default_factory=time.time,
    )


class ReconcilerReport(BaseModel):
    total_records: int = 0
    total_reconciliations: int = 0
    total_discrepancy_amount: float = 0.0
    by_provider: dict[str, int] = Field(
        default_factory=dict,
    )
    by_type: dict[str, int] = Field(
        default_factory=dict,
    )
    by_status: dict[str, int] = Field(
        default_factory=dict,
    )
    top_discrepancies: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(
        default_factory=time.time,
    )


# --- Reconciler ---


class CloudBillingReconciler:
    """Reconcile cloud billing against expected costs."""

    def __init__(
        self,
        max_records: int = 500000,
        discrepancy_threshold_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._discrepancy_threshold_pct = discrepancy_threshold_pct
        self._items: list[BillingRecord] = []
        self._results: list[ReconciliationResult] = []
        logger.info(
            "billing_reconciler.initialized",
            max_records=max_records,
            discrepancy_threshold_pct=(discrepancy_threshold_pct),
        )

    # -- record --

    def record_billing(
        self,
        provider: BillingProvider = (BillingProvider.AWS),
        account_id: str = "",
        service_name: str = "",
        expected_cost: float = 0.0,
        actual_cost: float = 0.0,
        billing_period: str = "",
        **kw: Any,
    ) -> BillingRecord:
        """Record a billing entry."""
        disc = round(actual_cost - expected_cost, 2)
        disc_type = self._classify_discrepancy(
            expected_cost,
            actual_cost,
            disc,
        )
        status = (
            ReconciliationStatus.MATCHED
            if disc_type is None
            else ReconciliationStatus.DISCREPANCY_FOUND
        )
        record = BillingRecord(
            provider=provider,
            account_id=account_id,
            service_name=service_name,
            expected_cost=expected_cost,
            actual_cost=actual_cost,
            discrepancy=disc,
            discrepancy_type=disc_type,
            status=status,
            billing_period=billing_period,
            **kw,
        )
        self._items.append(record)
        if len(self._items) > self._max_records:
            self._items = self._items[-self._max_records :]
        logger.info(
            "billing_reconciler.recorded",
            record_id=record.id,
            provider=provider,
            discrepancy=disc,
        )
        return record

    # -- get / list --

    def get_record(
        self,
        record_id: str,
    ) -> BillingRecord | None:
        """Get a single record by ID."""
        for item in self._items:
            if item.id == record_id:
                return item
        return None

    def list_records(
        self,
        provider: BillingProvider | None = None,
        status: ReconciliationStatus | None = None,
        limit: int = 50,
    ) -> list[BillingRecord]:
        """List records with optional filters."""
        results = list(self._items)
        if provider is not None:
            results = [r for r in results if r.provider == provider]
        if status is not None:
            results = [r for r in results if r.status == status]
        return results[-limit:]

    # -- domain operations --

    def reconcile_period(
        self,
        billing_period: str,
    ) -> ReconciliationResult:
        """Reconcile all records for a billing period."""
        records = [r for r in self._items if r.billing_period == billing_period]
        total_expected = sum(r.expected_cost for r in records)
        total_actual = sum(r.actual_cost for r in records)
        total_disc = round(
            total_actual - total_expected,
            2,
        )
        disc_count = sum(1 for r in records if r.discrepancy_type is not None)
        status = (
            ReconciliationStatus.MATCHED
            if disc_count == 0
            else ReconciliationStatus.DISCREPANCY_FOUND
        )
        result = ReconciliationResult(
            billing_period=billing_period,
            total_expected=total_expected,
            total_actual=total_actual,
            total_discrepancy=total_disc,
            discrepancy_count=disc_count,
            status=status,
        )
        self._results.append(result)
        logger.info(
            "billing_reconciler.period_reconciled",
            period=billing_period,
            discrepancy=total_disc,
        )
        return result

    def detect_discrepancies(
        self,
    ) -> list[BillingRecord]:
        """Return all records with discrepancies."""
        return [r for r in self._items if r.discrepancy_type is not None]

    def flag_unexpected_charges(
        self,
    ) -> list[BillingRecord]:
        """Flag records where actual cost exists but no expected cost."""
        unexpected: list[BillingRecord] = []
        for r in self._items:
            if r.expected_cost == 0.0 and r.actual_cost > 0.0:
                r.discrepancy_type = DiscrepancyType.UNEXPECTED_SERVICE
                r.status = ReconciliationStatus.DISCREPANCY_FOUND
                unexpected.append(r)
        return unexpected

    def calculate_accuracy_rate(self) -> float:
        """Calculate billing accuracy percentage."""
        if not self._items:
            return 100.0
        matched = sum(1 for r in self._items if r.status == ReconciliationStatus.MATCHED)
        total = len(self._items)
        return round(matched / total * 100, 2)

    def estimate_annual_leakage(self) -> float:
        """Estimate annualized billing leakage."""
        discs = [abs(r.discrepancy) for r in self._items if r.discrepancy_type is not None]
        if not discs:
            return 0.0
        # Assume records span ~1 month, project x12
        monthly = sum(discs)
        return round(monthly * 12, 2)

    # -- report --

    def generate_reconciler_report(
        self,
    ) -> ReconcilerReport:
        """Generate a comprehensive reconciler report."""
        by_provider: dict[str, int] = {}
        for r in self._items:
            key = r.provider.value
            by_provider[key] = by_provider.get(key, 0) + 1
        by_type: dict[str, int] = {}
        for r in self._items:
            if r.discrepancy_type is not None:
                key = r.discrepancy_type.value
                by_type[key] = by_type.get(key, 0) + 1
        by_status: dict[str, int] = {}
        for r in self._items:
            key = r.status.value
            by_status[key] = by_status.get(key, 0) + 1
        total_disc = sum(abs(r.discrepancy) for r in self._items if r.discrepancy_type is not None)
        # Top discrepancies by absolute value
        sorted_recs = sorted(
            self._items,
            key=lambda x: abs(x.discrepancy),
            reverse=True,
        )
        top = [r.service_name for r in sorted_recs[:5] if r.discrepancy_type is not None]
        recs = self._build_recommendations(
            total_disc,
            by_type,
        )
        return ReconcilerReport(
            total_records=len(self._items),
            total_reconciliations=len(self._results),
            total_discrepancy_amount=round(total_disc, 2),
            by_provider=by_provider,
            by_type=by_type,
            by_status=by_status,
            top_discrepancies=top,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all records and results."""
        count = len(self._items)
        self._items.clear()
        self._results.clear()
        logger.info(
            "billing_reconciler.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        provider_dist: dict[str, int] = {}
        for r in self._items:
            key = r.provider.value
            provider_dist[key] = provider_dist.get(key, 0) + 1
        return {
            "total_records": len(self._items),
            "total_reconciliations": len(self._results),
            "discrepancy_threshold_pct": (self._discrepancy_threshold_pct),
            "accuracy_rate": (self.calculate_accuracy_rate()),
            "provider_distribution": provider_dist,
        }

    # -- internal helpers --

    def _classify_discrepancy(
        self,
        expected: float,
        actual: float,
        disc: float,
    ) -> DiscrepancyType | None:
        if expected == 0.0 and actual == 0.0:
            return None
        if expected == 0.0 and actual > 0.0:
            return DiscrepancyType.UNEXPECTED_SERVICE
        threshold = expected * self._discrepancy_threshold_pct / 100
        if abs(disc) <= threshold:
            return None
        if disc > 0:
            return DiscrepancyType.OVERCHARGE
        return DiscrepancyType.UNDERCHARGE

    def _build_recommendations(
        self,
        total_disc: float,
        by_type: dict[str, int],
    ) -> list[str]:
        recs: list[str] = []
        if total_disc > 1000:
            recs.append(f"${total_disc:,.2f} total discrepancy - investigate")
        overcharges = by_type.get("overcharge", 0)
        if overcharges > 0:
            recs.append(f"{overcharges} overcharge(s) detected - file disputes")
        unexpected = by_type.get(
            "unexpected_service",
            0,
        )
        if unexpected > 0:
            recs.append(f"{unexpected} unexpected service charge(s)")
        if not recs:
            recs.append("Billing reconciliation clean")
        return recs
