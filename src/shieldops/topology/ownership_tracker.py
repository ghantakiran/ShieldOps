"""Service Ownership Tracker — track service ownership and identify orphaned services."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class OwnershipRole(StrEnum):
    PRIMARY_OWNER = "primary_owner"
    SECONDARY_OWNER = "secondary_owner"
    ON_CALL = "on_call"
    CONTRIBUTOR = "contributor"
    STAKEHOLDER = "stakeholder"


class OwnershipStatus(StrEnum):
    ACTIVE = "active"
    TRANSITIONING = "transitioning"
    ORPHANED = "orphaned"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class EscalationLevel(StrEnum):
    TEAM = "team"
    ENGINEERING_LEAD = "engineering_lead"
    DIRECTOR = "director"
    VP = "vp"
    CTO = "cto"


# --- Models ---


class OwnershipRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    role: OwnershipRole = OwnershipRole.PRIMARY_OWNER
    status: OwnershipStatus = OwnershipStatus.ACTIVE
    escalation: EscalationLevel = EscalationLevel.TEAM
    tenure_days: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class OwnershipTransfer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transfer_name: str = ""
    role: OwnershipRole = OwnershipRole.PRIMARY_OWNER
    status: OwnershipStatus = OwnershipStatus.ACTIVE
    from_team: str = ""
    to_team: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceOwnershipReport(BaseModel):
    total_ownerships: int = 0
    total_transfers: int = 0
    active_rate_pct: float = 0.0
    by_role: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    orphan_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceOwnershipTracker:
    """Track service ownership and identify orphaned services."""

    def __init__(
        self,
        max_records: int = 200000,
        max_orphan_days: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._max_orphan_days = max_orphan_days
        self._records: list[OwnershipRecord] = []
        self._transfers: list[OwnershipTransfer] = []
        logger.info(
            "ownership_tracker.initialized",
            max_records=max_records,
            max_orphan_days=max_orphan_days,
        )

    # -- record / get / list ---------------------------------------------

    def record_ownership(
        self,
        service_name: str,
        role: OwnershipRole = OwnershipRole.PRIMARY_OWNER,
        status: OwnershipStatus = OwnershipStatus.ACTIVE,
        escalation: EscalationLevel = EscalationLevel.TEAM,
        tenure_days: float = 0.0,
        details: str = "",
    ) -> OwnershipRecord:
        record = OwnershipRecord(
            service_name=service_name,
            role=role,
            status=status,
            escalation=escalation,
            tenure_days=tenure_days,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "ownership_tracker.ownership_recorded",
            record_id=record.id,
            service_name=service_name,
            role=role.value,
            status=status.value,
        )
        return record

    def get_ownership(self, record_id: str) -> OwnershipRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_ownerships(
        self,
        service_name: str | None = None,
        role: OwnershipRole | None = None,
        limit: int = 50,
    ) -> list[OwnershipRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if role is not None:
            results = [r for r in results if r.role == role]
        return results[-limit:]

    def add_transfer(
        self,
        transfer_name: str,
        role: OwnershipRole = OwnershipRole.PRIMARY_OWNER,
        status: OwnershipStatus = OwnershipStatus.ACTIVE,
        from_team: str = "",
        to_team: str = "",
    ) -> OwnershipTransfer:
        transfer = OwnershipTransfer(
            transfer_name=transfer_name,
            role=role,
            status=status,
            from_team=from_team,
            to_team=to_team,
        )
        self._transfers.append(transfer)
        if len(self._transfers) > self._max_records:
            self._transfers = self._transfers[-self._max_records :]
        logger.info(
            "ownership_tracker.transfer_added",
            transfer_name=transfer_name,
            role=role.value,
            status=status.value,
        )
        return transfer

    # -- domain operations -----------------------------------------------

    def analyze_ownership_health(self, service_name: str) -> dict[str, Any]:
        """Analyze ownership health for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        active_count = sum(1 for r in records if r.status == OwnershipStatus.ACTIVE)
        active_rate = round(active_count / len(records) * 100, 2)
        avg_tenure = round(sum(r.tenure_days for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "active_rate": active_rate,
            "record_count": len(records),
            "avg_tenure": avg_tenure,
        }

    def identify_orphaned_services(self) -> list[dict[str, Any]]:
        """Find services with >1 ORPHANED or DEPRECATED status."""
        orphan_counts: dict[str, int] = {}
        for r in self._records:
            if r.status in (OwnershipStatus.ORPHANED, OwnershipStatus.DEPRECATED):
                orphan_counts[r.service_name] = orphan_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in orphan_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "orphan_count": count,
                    }
                )
        results.sort(key=lambda x: x["orphan_count"], reverse=True)
        return results

    def rank_by_ownership_stability(self) -> list[dict[str, Any]]:
        """Rank services by avg tenure_days descending."""
        tenures: dict[str, list[float]] = {}
        for r in self._records:
            tenures.setdefault(r.service_name, []).append(r.tenure_days)
        results: list[dict[str, Any]] = []
        for svc, tn in tenures.items():
            avg = round(sum(tn) / len(tn), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_tenure_days": avg,
                }
            )
        results.sort(key=lambda x: x["avg_tenure_days"], reverse=True)
        return results

    def detect_ownership_gaps(self) -> list[dict[str, Any]]:
        """Detect services with >3 non-ACTIVE records."""
        svc_non_active: dict[str, int] = {}
        for r in self._records:
            if r.status != OwnershipStatus.ACTIVE:
                svc_non_active[r.service_name] = svc_non_active.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_non_active.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "non_active_count": count,
                        "gap_detected": True,
                    }
                )
        results.sort(key=lambda x: x["non_active_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ServiceOwnershipReport:
        by_role: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_role[r.role.value] = by_role.get(r.role.value, 0) + 1
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
        active_count = sum(1 for r in self._records if r.status == OwnershipStatus.ACTIVE)
        active_rate = round(active_count / len(self._records) * 100, 2) if self._records else 0.0
        orphan_count = len(self.identify_orphaned_services())
        recs: list[str] = []
        if self._records and active_rate < 80.0:
            recs.append(f"Active rate {active_rate}% is below 80% threshold")
        if orphan_count > 0:
            recs.append(f"{orphan_count} service(s) with orphaned ownership")
        gaps = len(self.detect_ownership_gaps())
        if gaps > 0:
            recs.append(f"{gaps} service(s) with ownership gaps")
        if not recs:
            recs.append("Service ownership health meets targets")
        return ServiceOwnershipReport(
            total_ownerships=len(self._records),
            total_transfers=len(self._transfers),
            active_rate_pct=active_rate,
            by_role=by_role,
            by_status=by_status,
            orphan_count=orphan_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._transfers.clear()
        logger.info("ownership_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        role_dist: dict[str, int] = {}
        for r in self._records:
            key = r.role.value
            role_dist[key] = role_dist.get(key, 0) + 1
        return {
            "total_ownerships": len(self._records),
            "total_transfers": len(self._transfers),
            "max_orphan_days": self._max_orphan_days,
            "role_distribution": role_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
