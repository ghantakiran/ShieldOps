"""Invoice Validation Engine — validate invoices, detect discrepancies, and anomalies."""

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
    MISSING_ITEM = "missing_item"
    DUPLICATE_CHARGE = "duplicate_charge"
    RATE_MISMATCH = "rate_mismatch"


class ValidationStatus(StrEnum):
    VALIDATED = "validated"
    DISCREPANCY_FOUND = "discrepancy_found"
    PENDING_REVIEW = "pending_review"
    DISPUTED = "disputed"
    RESOLVED = "resolved"


class InvoiceCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    SUPPORT = "support"


# --- Models ---


class InvoiceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invoice_id: str = ""
    discrepancy_type: DiscrepancyType = DiscrepancyType.OVERCHARGE
    validation_status: ValidationStatus = ValidationStatus.PENDING_REVIEW
    invoice_category: InvoiceCategory = InvoiceCategory.COMPUTE
    discrepancy_amount: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DiscrepancyDetail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detail_name: str = ""
    discrepancy_type: DiscrepancyType = DiscrepancyType.OVERCHARGE
    amount_threshold: float = 0.0
    avg_discrepancy_amount: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class InvoiceValidationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_discrepancies: int = 0
    high_discrepancies: int = 0
    avg_discrepancy_amount: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    top_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class InvoiceValidationEngine:
    """Validate invoices, detect discrepancies, and identify billing anomalies."""

    def __init__(
        self,
        max_records: int = 200000,
        max_discrepancy_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_discrepancy_pct = max_discrepancy_pct
        self._records: list[InvoiceRecord] = []
        self._discrepancies: list[DiscrepancyDetail] = []
        logger.info(
            "invoice_validator.initialized",
            max_records=max_records,
            max_discrepancy_pct=max_discrepancy_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_invoice(
        self,
        invoice_id: str,
        discrepancy_type: DiscrepancyType = DiscrepancyType.OVERCHARGE,
        validation_status: ValidationStatus = ValidationStatus.PENDING_REVIEW,
        invoice_category: InvoiceCategory = InvoiceCategory.COMPUTE,
        discrepancy_amount: float = 0.0,
        team: str = "",
    ) -> InvoiceRecord:
        record = InvoiceRecord(
            invoice_id=invoice_id,
            discrepancy_type=discrepancy_type,
            validation_status=validation_status,
            invoice_category=invoice_category,
            discrepancy_amount=discrepancy_amount,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "invoice_validator.invoice_recorded",
            record_id=record.id,
            invoice_id=invoice_id,
            discrepancy_type=discrepancy_type.value,
            validation_status=validation_status.value,
        )
        return record

    def get_invoice(self, record_id: str) -> InvoiceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_invoices(
        self,
        dtype: DiscrepancyType | None = None,
        status: ValidationStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[InvoiceRecord]:
        results = list(self._records)
        if dtype is not None:
            results = [r for r in results if r.discrepancy_type == dtype]
        if status is not None:
            results = [r for r in results if r.validation_status == status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_discrepancy(
        self,
        detail_name: str,
        discrepancy_type: DiscrepancyType = DiscrepancyType.OVERCHARGE,
        amount_threshold: float = 0.0,
        avg_discrepancy_amount: float = 0.0,
        description: str = "",
    ) -> DiscrepancyDetail:
        detail = DiscrepancyDetail(
            detail_name=detail_name,
            discrepancy_type=discrepancy_type,
            amount_threshold=amount_threshold,
            avg_discrepancy_amount=avg_discrepancy_amount,
            description=description,
        )
        self._discrepancies.append(detail)
        if len(self._discrepancies) > self._max_records:
            self._discrepancies = self._discrepancies[-self._max_records :]
        logger.info(
            "invoice_validator.discrepancy_added",
            detail_name=detail_name,
            discrepancy_type=discrepancy_type.value,
            amount_threshold=amount_threshold,
        )
        return detail

    # -- domain operations --------------------------------------------------

    def analyze_discrepancy_patterns(self) -> dict[str, Any]:
        """Group by type; return count and avg discrepancy amount per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.discrepancy_type.value
            type_data.setdefault(key, []).append(r.discrepancy_amount)
        result: dict[str, Any] = {}
        for dtype, amounts in type_data.items():
            result[dtype] = {
                "count": len(amounts),
                "avg_discrepancy_amount": round(sum(amounts) / len(amounts), 2),
            }
        return result

    def identify_high_discrepancies(self) -> list[dict[str, Any]]:
        """Return records where status is DISCREPANCY_FOUND or DISPUTED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.validation_status in (
                ValidationStatus.DISCREPANCY_FOUND,
                ValidationStatus.DISPUTED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "invoice_id": r.invoice_id,
                        "discrepancy_type": r.discrepancy_type.value,
                        "discrepancy_amount": r.discrepancy_amount,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_discrepancy_amount(self) -> list[dict[str, Any]]:
        """Group by team, avg discrepancy amount, sort descending."""
        team_amounts: dict[str, list[float]] = {}
        for r in self._records:
            team_amounts.setdefault(r.team, []).append(r.discrepancy_amount)
        results: list[dict[str, Any]] = []
        for team, amounts in team_amounts.items():
            results.append(
                {
                    "team": team,
                    "avg_discrepancy_amount": round(sum(amounts) / len(amounts), 2),
                    "count": len(amounts),
                }
            )
        results.sort(key=lambda x: x["avg_discrepancy_amount"], reverse=True)
        return results

    def detect_billing_anomalies(self) -> dict[str, Any]:
        """Split-half on avg_discrepancy_amount; delta threshold 5.0."""
        if len(self._discrepancies) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        amounts = [d.avg_discrepancy_amount for d in self._discrepancies]
        mid = len(amounts) // 2
        first_half = amounts[:mid]
        second_half = amounts[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> InvoiceValidationReport:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            by_type[r.discrepancy_type.value] = by_type.get(r.discrepancy_type.value, 0) + 1
            by_status[r.validation_status.value] = by_status.get(r.validation_status.value, 0) + 1
            by_category[r.invoice_category.value] = by_category.get(r.invoice_category.value, 0) + 1
        high_count = sum(
            1
            for r in self._records
            if r.validation_status
            in (ValidationStatus.DISCREPANCY_FOUND, ValidationStatus.DISPUTED)
        )
        avg_amount = (
            round(sum(r.discrepancy_amount for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_discrepancy_amount()
        top_items = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if avg_amount > self._max_discrepancy_pct:
            recs.append(
                f"Avg discrepancy amount {avg_amount} exceeds "
                f"threshold ({self._max_discrepancy_pct}%)"
            )
        if high_count > 0:
            recs.append(f"{high_count} high discrepancy(ies) detected — review invoices")
        if not recs:
            recs.append("Invoice discrepancies are within acceptable limits")
        return InvoiceValidationReport(
            total_records=len(self._records),
            total_discrepancies=len(self._discrepancies),
            high_discrepancies=high_count,
            avg_discrepancy_amount=avg_amount,
            by_type=by_type,
            by_status=by_status,
            by_category=by_category,
            top_items=top_items,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._discrepancies.clear()
        logger.info("invoice_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.discrepancy_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_discrepancies": len(self._discrepancies),
            "max_discrepancy_pct": self._max_discrepancy_pct,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_invoices": len({r.invoice_id for r in self._records}),
        }
