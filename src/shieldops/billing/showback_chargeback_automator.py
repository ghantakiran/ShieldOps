"""Showback Chargeback Automator
compute allocation models, detect allocation drift,
generate chargeback invoices."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AllocationMethod(StrEnum):
    TAG_BASED = "tag_based"
    PROPORTIONAL = "proportional"
    USAGE_WEIGHTED = "usage_weighted"
    FIXED = "fixed"


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    SENT = "sent"


class DriftSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class ChargebackRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    allocation_method: AllocationMethod = AllocationMethod.TAG_BASED
    invoice_status: InvoiceStatus = InvoiceStatus.DRAFT
    drift_severity: DriftSeverity = DriftSeverity.LOW
    allocated_cost: float = 0.0
    actual_cost: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChargebackAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team_id: str = ""
    allocation_method: AllocationMethod = AllocationMethod.TAG_BASED
    drift_pct: float = 0.0
    drift_severity: DriftSeverity = DriftSeverity.LOW
    invoice_amount: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChargebackReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    total_allocated: float = 0.0
    by_allocation_method: dict[str, int] = Field(default_factory=dict)
    by_invoice_status: dict[str, int] = Field(default_factory=dict)
    by_drift_severity: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ShowbackChargebackAutomator:
    """Compute allocation models, detect drift,
    generate chargeback invoices."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ChargebackRecord] = []
        self._analyses: dict[str, ChargebackAnalysis] = {}
        logger.info(
            "showback_chargeback.init",
            max_records=max_records,
        )

    def add_record(
        self,
        team_id: str = "",
        allocation_method: AllocationMethod = (AllocationMethod.TAG_BASED),
        invoice_status: InvoiceStatus = (InvoiceStatus.DRAFT),
        drift_severity: DriftSeverity = (DriftSeverity.LOW),
        allocated_cost: float = 0.0,
        actual_cost: float = 0.0,
        description: str = "",
    ) -> ChargebackRecord:
        record = ChargebackRecord(
            team_id=team_id,
            allocation_method=allocation_method,
            invoice_status=invoice_status,
            drift_severity=drift_severity,
            allocated_cost=allocated_cost,
            actual_cost=actual_cost,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "showback_chargeback.record_added",
            record_id=record.id,
            team_id=team_id,
        )
        return record

    def process(self, key: str) -> ChargebackAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        drift = 0.0
        if rec.allocated_cost > 0:
            drift = round(
                abs(rec.actual_cost - rec.allocated_cost) / rec.allocated_cost * 100,
                2,
            )
        analysis = ChargebackAnalysis(
            team_id=rec.team_id,
            allocation_method=rec.allocation_method,
            drift_pct=drift,
            drift_severity=rec.drift_severity,
            invoice_amount=rec.actual_cost,
            description=(f"Team {rec.team_id} drift {drift}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ChargebackReport:
        by_am: dict[str, int] = {}
        by_is: dict[str, int] = {}
        by_ds: dict[str, int] = {}
        total_alloc = 0.0
        for r in self._records:
            k = r.allocation_method.value
            by_am[k] = by_am.get(k, 0) + 1
            k2 = r.invoice_status.value
            by_is[k2] = by_is.get(k2, 0) + 1
            k3 = r.drift_severity.value
            by_ds[k3] = by_ds.get(k3, 0) + 1
            total_alloc += r.allocated_cost
        recs: list[str] = []
        crit = [r for r in self._records if r.drift_severity == DriftSeverity.CRITICAL]
        if crit:
            recs.append(f"{len(crit)} critical allocation drifts detected")
        if not recs:
            recs.append("Allocations within norms")
        return ChargebackReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            total_allocated=round(total_alloc, 2),
            by_allocation_method=by_am,
            by_invoice_status=by_is,
            by_drift_severity=by_ds,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        am_dist: dict[str, int] = {}
        for r in self._records:
            k = r.allocation_method.value
            am_dist[k] = am_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "allocation_method_dist": am_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("showback_chargeback.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_allocation_model(
        self,
    ) -> list[dict[str, Any]]:
        """Compute allocation per team."""
        team_alloc: dict[str, float] = {}
        team_actual: dict[str, float] = {}
        for r in self._records:
            team_alloc[r.team_id] = team_alloc.get(r.team_id, 0.0) + r.allocated_cost
            team_actual[r.team_id] = team_actual.get(r.team_id, 0.0) + r.actual_cost
        results: list[dict[str, Any]] = []
        for tid, alloc in team_alloc.items():
            actual = team_actual.get(tid, 0.0)
            results.append(
                {
                    "team_id": tid,
                    "allocated": round(alloc, 2),
                    "actual": round(actual, 2),
                    "variance": round(actual - alloc, 2),
                }
            )
        results.sort(
            key=lambda x: abs(x["variance"]),
            reverse=True,
        )
        return results

    def detect_allocation_drift(
        self,
    ) -> list[dict[str, Any]]:
        """Detect drift between allocated/actual."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.team_id not in seen:
                seen.add(r.team_id)
                drift = 0.0
                if r.allocated_cost > 0:
                    drift = round(
                        abs(r.actual_cost - r.allocated_cost) / r.allocated_cost * 100,
                        2,
                    )
                results.append(
                    {
                        "team_id": r.team_id,
                        "drift_pct": drift,
                        "severity": (r.drift_severity.value),
                    }
                )
        results.sort(
            key=lambda x: x["drift_pct"],
            reverse=True,
        )
        return results

    def generate_chargeback_invoice(
        self,
    ) -> list[dict[str, Any]]:
        """Generate invoices per team."""
        team_costs: dict[str, float] = {}
        for r in self._records:
            team_costs[r.team_id] = team_costs.get(r.team_id, 0.0) + r.actual_cost
        results: list[dict[str, Any]] = []
        for tid, total in team_costs.items():
            results.append(
                {
                    "team_id": tid,
                    "invoice_amount": round(total, 2),
                    "status": "draft",
                    "invoice_id": str(uuid.uuid4())[:8],
                }
            )
        results.sort(
            key=lambda x: x["invoice_amount"],
            reverse=True,
        )
        return results
