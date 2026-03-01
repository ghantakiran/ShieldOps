"""Platform Availability Tracker — track service availability and outages."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AvailabilityStatus(StrEnum):
    FULLY_AVAILABLE = "fully_available"
    PARTIALLY_DEGRADED = "partially_degraded"
    MAJOR_OUTAGE = "major_outage"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class OutageCategory(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    NETWORK = "network"
    DATABASE = "database"
    THIRD_PARTY = "third_party"


class AvailabilityTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class AvailabilityRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    service: str = ""
    availability_pct: float = 100.0
    status: AvailabilityStatus = AvailabilityStatus.FULLY_AVAILABLE
    outage_minutes: float = 0.0
    category: OutageCategory = OutageCategory.INFRASTRUCTURE
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class OutageEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    service: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    duration_minutes: float = 0.0
    category: OutageCategory = OutageCategory.INFRASTRUCTURE
    root_cause: str = ""
    created_at: float = Field(default_factory=time.time)


class AvailabilityReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_outages: int = 0
    avg_availability_pct: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    below_target_services: list[str] = Field(default_factory=list)
    longest_outages: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PlatformAvailabilityTracker:
    """Track service availability and outage events."""

    def __init__(
        self,
        max_records: int = 200000,
        min_availability_pct: float = 99.9,
    ) -> None:
        self._max_records = max_records
        self._min_availability_pct = min_availability_pct
        self._records: list[AvailabilityRecord] = []
        self._outages: list[OutageEvent] = []
        logger.info(
            "availability_tracker.initialized",
            max_records=max_records,
            min_availability_pct=min_availability_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_availability(
        self,
        service: str,
        availability_pct: float = 100.0,
        status: AvailabilityStatus = (AvailabilityStatus.FULLY_AVAILABLE),
        outage_minutes: float = 0.0,
        category: OutageCategory = (OutageCategory.INFRASTRUCTURE),
        team: str = "",
        details: str = "",
    ) -> AvailabilityRecord:
        record = AvailabilityRecord(
            service=service,
            availability_pct=availability_pct,
            status=status,
            outage_minutes=outage_minutes,
            category=category,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "availability_tracker.recorded",
            record_id=record.id,
            service=service,
            availability_pct=availability_pct,
            status=status.value,
        )
        return record

    def get_availability(self, record_id: str) -> AvailabilityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_availabilities(
        self,
        status: AvailabilityStatus | None = None,
        category: OutageCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AvailabilityRecord]:
        results = list(self._records)
        if status is not None:
            results = [r for r in results if r.status == status]
        if category is not None:
            results = [r for r in results if r.category == category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_outage(
        self,
        service: str,
        start_time: float = 0.0,
        end_time: float = 0.0,
        duration_minutes: float = 0.0,
        category: OutageCategory = (OutageCategory.INFRASTRUCTURE),
        root_cause: str = "",
    ) -> OutageEvent:
        outage = OutageEvent(
            service=service,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            category=category,
            root_cause=root_cause,
        )
        self._outages.append(outage)
        if len(self._outages) > self._max_records:
            self._outages = self._outages[-self._max_records :]
        logger.info(
            "availability_tracker.outage_added",
            outage_id=outage.id,
            service=service,
            category=category.value,
        )
        return outage

    # -- domain operations -------------------------------------------

    def analyze_availability_by_service(
        self,
    ) -> list[dict[str, Any]]:
        """Average availability per service."""
        svc_avails: dict[str, list[float]] = {}
        for r in self._records:
            svc_avails.setdefault(r.service, []).append(r.availability_pct)
        results: list[dict[str, Any]] = []
        for svc, avails in svc_avails.items():
            avg = round(sum(avails) / len(avails), 2)
            results.append(
                {
                    "service": svc,
                    "avg_availability_pct": avg,
                    "samples": len(avails),
                }
            )
        results.sort(key=lambda x: x["avg_availability_pct"])
        return results

    def identify_below_target_services(
        self,
    ) -> list[dict[str, Any]]:
        """Find services below min availability threshold."""
        svc_avails: dict[str, list[float]] = {}
        for r in self._records:
            svc_avails.setdefault(r.service, []).append(r.availability_pct)
        results: list[dict[str, Any]] = []
        for svc, avails in svc_avails.items():
            avg = round(sum(avails) / len(avails), 2)
            if avg < self._min_availability_pct:
                results.append(
                    {
                        "service": svc,
                        "avg_availability_pct": avg,
                        "target": (self._min_availability_pct),
                    }
                )
        results.sort(key=lambda x: x["avg_availability_pct"])
        return results

    def rank_by_availability(
        self,
    ) -> list[dict[str, Any]]:
        """Rank services by average availability, desc."""
        svc_avails: dict[str, list[float]] = {}
        for r in self._records:
            svc_avails.setdefault(r.service, []).append(r.availability_pct)
        results: list[dict[str, Any]] = []
        for svc, avails in svc_avails.items():
            avg = round(sum(avails) / len(avails), 2)
            results.append(
                {
                    "service": svc,
                    "avg_availability_pct": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_availability_pct"],
            reverse=True,
        )
        return results

    def detect_availability_trends(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with >3 records (trending)."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service] = svc_counts.get(r.service, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service": svc,
                        "record_count": count,
                    }
                )
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> AvailabilityReport:
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for r in self._records:
            st = r.status.value
            by_status[st] = by_status.get(st, 0) + 1
            cat = r.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
        avg_avail = (
            round(
                sum(r.availability_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        below = self.identify_below_target_services()
        below_names = [b["service"] for b in below[:10]]
        # longest outages
        sorted_outages = sorted(
            self._outages,
            key=lambda o: o.duration_minutes,
            reverse=True,
        )
        longest = [o.service for o in sorted_outages[:10]]
        recs: list[str] = []
        if below_names:
            recs.append(f"{len(below_names)} service(s) below {self._min_availability_pct}% target")
        outage_count = sum(1 for r in self._records if r.status == AvailabilityStatus.MAJOR_OUTAGE)
        if outage_count > 0:
            recs.append(f"{outage_count} major outage(s) recorded")
        if not recs:
            recs.append("Availability levels within acceptable limits")
        return AvailabilityReport(
            total_records=len(self._records),
            total_outages=len(self._outages),
            avg_availability_pct=avg_avail,
            by_status=by_status,
            by_category=by_category,
            below_target_services=below_names,
            longest_outages=longest,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._outages.clear()
        logger.info("availability_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_outages": len(self._outages),
            "min_availability_pct": (self._min_availability_pct),
            "status_distribution": status_dist,
            "unique_services": len({r.service for r in self._records}),
        }
