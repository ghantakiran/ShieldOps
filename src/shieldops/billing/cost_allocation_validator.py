"""Cost Allocation Validator — validate cost allocations and accuracy."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AllocationStatus(StrEnum):
    VALID = "valid"
    MISATTRIBUTED = "misattributed"
    UNALLOCATED = "unallocated"
    DISPUTED = "disputed"
    PENDING = "pending"


class AllocationMethod(StrEnum):
    TAG_BASED = "tag_based"
    USAGE_BASED = "usage_based"
    PROPORTIONAL = "proportional"
    FIXED = "fixed"
    HYBRID = "hybrid"


class CostCenter(StrEnum):
    ENGINEERING = "engineering"
    OPERATIONS = "operations"
    SECURITY = "security"
    DATA = "data"
    INFRASTRUCTURE = "infrastructure"


# --- Models ---


class AllocationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    allocation_id: str = ""
    allocation_status: AllocationStatus = AllocationStatus.PENDING
    allocation_method: AllocationMethod = AllocationMethod.TAG_BASED
    cost_center: CostCenter = CostCenter.ENGINEERING
    accuracy_pct: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class AllocationCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    allocation_id: str = ""
    allocation_status: AllocationStatus = AllocationStatus.PENDING
    check_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostAllocationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_checks: int = 0
    invalid_count: int = 0
    avg_accuracy_pct: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_center: dict[str, int] = Field(default_factory=dict)
    top_invalid: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostAllocationValidator:
    """Validate cost allocations, detect misattributed costs."""

    def __init__(
        self,
        max_records: int = 200000,
        min_accuracy_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_accuracy_pct = min_accuracy_pct
        self._records: list[AllocationRecord] = []
        self._checks: list[AllocationCheck] = []
        logger.info(
            "cost_allocation_validator.initialized",
            max_records=max_records,
            min_accuracy_pct=min_accuracy_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_allocation(
        self,
        allocation_id: str,
        allocation_status: AllocationStatus = AllocationStatus.PENDING,
        allocation_method: AllocationMethod = AllocationMethod.TAG_BASED,
        cost_center: CostCenter = CostCenter.ENGINEERING,
        accuracy_pct: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> AllocationRecord:
        record = AllocationRecord(
            allocation_id=allocation_id,
            allocation_status=allocation_status,
            allocation_method=allocation_method,
            cost_center=cost_center,
            accuracy_pct=accuracy_pct,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_allocation_validator.allocation_recorded",
            record_id=record.id,
            allocation_id=allocation_id,
            allocation_status=allocation_status.value,
            allocation_method=allocation_method.value,
        )
        return record

    def get_allocation(self, record_id: str) -> AllocationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_allocations(
        self,
        allocation_status: AllocationStatus | None = None,
        allocation_method: AllocationMethod | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AllocationRecord]:
        results = list(self._records)
        if allocation_status is not None:
            results = [r for r in results if r.allocation_status == allocation_status]
        if allocation_method is not None:
            results = [r for r in results if r.allocation_method == allocation_method]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_check(
        self,
        allocation_id: str,
        allocation_status: AllocationStatus = AllocationStatus.PENDING,
        check_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> AllocationCheck:
        check = AllocationCheck(
            allocation_id=allocation_id,
            allocation_status=allocation_status,
            check_score=check_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._checks.append(check)
        if len(self._checks) > self._max_records:
            self._checks = self._checks[-self._max_records :]
        logger.info(
            "cost_allocation_validator.check_added",
            allocation_id=allocation_id,
            allocation_status=allocation_status.value,
            check_score=check_score,
        )
        return check

    # -- domain operations --------------------------------------------------

    def analyze_allocation_distribution(self) -> dict[str, Any]:
        """Group by allocation_status; return count and avg accuracy."""
        status_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.allocation_status.value
            status_data.setdefault(key, []).append(r.accuracy_pct)
        result: dict[str, Any] = {}
        for status, scores in status_data.items():
            result[status] = {
                "count": len(scores),
                "avg_accuracy_pct": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_invalid_allocations(self) -> list[dict[str, Any]]:
        """Return allocations where status is MISATTRIBUTED or UNALLOCATED."""
        invalid_statuses = {
            AllocationStatus.MISATTRIBUTED,
            AllocationStatus.UNALLOCATED,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.allocation_status in invalid_statuses:
                results.append(
                    {
                        "record_id": r.id,
                        "allocation_id": r.allocation_id,
                        "allocation_status": r.allocation_status.value,
                        "allocation_method": r.allocation_method.value,
                        "accuracy_pct": r.accuracy_pct,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["accuracy_pct"], reverse=False)
        return results

    def rank_by_accuracy(self) -> list[dict[str, Any]]:
        """Group by service, avg accuracy_pct, sort asc (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.accuracy_pct)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_accuracy_pct": round(sum(scores) / len(scores), 2),
                    "allocation_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_accuracy_pct"], reverse=False)
        return results

    def detect_allocation_trends(self) -> dict[str, Any]:
        """Split-half comparison on check_score; delta 5.0."""
        if len(self._checks) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [c.check_score for c in self._checks]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> CostAllocationReport:
        by_status: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_center: dict[str, int] = {}
        for r in self._records:
            by_status[r.allocation_status.value] = by_status.get(r.allocation_status.value, 0) + 1
            by_method[r.allocation_method.value] = by_method.get(r.allocation_method.value, 0) + 1
            by_center[r.cost_center.value] = by_center.get(r.cost_center.value, 0) + 1
        invalid_count = sum(
            1
            for r in self._records
            if r.allocation_status
            in {
                AllocationStatus.MISATTRIBUTED,
                AllocationStatus.UNALLOCATED,
            }
        )
        avg_accuracy = (
            round(
                sum(r.accuracy_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        invalid = self.identify_invalid_allocations()
        top_invalid = [i["allocation_id"] for i in invalid]
        recs: list[str] = []
        if invalid:
            recs.append(f"{len(invalid)} invalid allocation(s) detected — review cost attribution")
        low_acc = sum(1 for r in self._records if r.accuracy_pct < self._min_accuracy_pct)
        if low_acc > 0:
            recs.append(
                f"{low_acc} allocation(s) below accuracy threshold ({self._min_accuracy_pct}%)"
            )
        if not recs:
            recs.append("Cost allocation levels are acceptable")
        return CostAllocationReport(
            total_records=len(self._records),
            total_checks=len(self._checks),
            invalid_count=invalid_count,
            avg_accuracy_pct=avg_accuracy,
            by_status=by_status,
            by_method=by_method,
            by_center=by_center,
            top_invalid=top_invalid,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._checks.clear()
        logger.info("cost_allocation_validator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.allocation_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_checks": len(self._checks),
            "min_accuracy_pct": self._min_accuracy_pct,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
