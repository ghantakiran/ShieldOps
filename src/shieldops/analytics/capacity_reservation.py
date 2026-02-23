"""Capacity reservation system for infrastructure resource planning.

Manages resource reservations across teams, validates time windows,
detects scheduling conflicts, and tracks utilization to support
infrastructure capacity planning workflows.
"""

from __future__ import annotations

import enum
import time
import uuid
from collections import defaultdict
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class ReservationStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ResourceType(enum.StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    INSTANCES = "instances"


# -- Models --------------------------------------------------------------------


class ReservationResource(BaseModel):
    resource_type: ResourceType
    amount: float
    unit: str = "cores"


class CapacityReservation(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    team: str = ""
    resources: list[ReservationResource] = Field(default_factory=list)
    start_time: float
    end_time: float
    status: ReservationStatus = ReservationStatus.PENDING
    reason: str = ""
    approved_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class ReservationConflict(BaseModel):
    reservation_id: str
    conflicting_id: str
    resource_type: ResourceType
    message: str = ""


# -- Manager -------------------------------------------------------------------


class CapacityReservationManager:
    """Manage infrastructure capacity reservations with conflict detection.

    Parameters
    ----------
    max_active:
        Maximum number of active/approved reservations allowed.
    max_duration_days:
        Maximum allowed reservation duration in days.
    """

    def __init__(
        self,
        max_active: int = 500,
        max_duration_days: int = 90,
    ) -> None:
        self._reservations: dict[str, CapacityReservation] = {}
        self._max_active = max_active
        self._max_duration_days = max_duration_days

    def create_reservation(
        self,
        name: str,
        resources: list[ReservationResource],
        start_time: float,
        end_time: float,
        team: str = "",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CapacityReservation:
        if end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        duration_days = (end_time - start_time) / 86400
        if duration_days > self._max_duration_days:
            raise ValueError(
                f"Reservation duration {duration_days:.1f}d exceeds max {self._max_duration_days}d"
            )
        active_count = sum(
            1
            for r in self._reservations.values()
            if r.status
            in (ReservationStatus.PENDING, ReservationStatus.APPROVED, ReservationStatus.ACTIVE)
        )
        if active_count >= self._max_active:
            raise ValueError(f"Maximum active reservations limit reached: {self._max_active}")
        reservation = CapacityReservation(
            name=name,
            team=team,
            resources=resources,
            start_time=start_time,
            end_time=end_time,
            reason=reason,
            metadata=metadata or {},
        )
        self._reservations[reservation.id] = reservation
        logger.info(
            "capacity_reservation_created",
            reservation_id=reservation.id,
            name=name,
            team=team,
        )
        return reservation

    def approve_reservation(
        self,
        reservation_id: str,
        approved_by: str = "",
    ) -> CapacityReservation | None:
        reservation = self._reservations.get(reservation_id)
        if reservation is None:
            return None
        if reservation.status != ReservationStatus.PENDING:
            return None
        reservation.status = ReservationStatus.APPROVED
        reservation.approved_by = approved_by
        logger.info(
            "reservation_approved",
            reservation_id=reservation_id,
            approved_by=approved_by,
        )
        return reservation

    def activate_reservation(
        self,
        reservation_id: str,
    ) -> CapacityReservation | None:
        reservation = self._reservations.get(reservation_id)
        if reservation is None:
            return None
        if reservation.status != ReservationStatus.APPROVED:
            return None
        reservation.status = ReservationStatus.ACTIVE
        logger.info("reservation_activated", reservation_id=reservation_id)
        return reservation

    def cancel_reservation(
        self,
        reservation_id: str,
    ) -> CapacityReservation | None:
        reservation = self._reservations.get(reservation_id)
        if reservation is None:
            return None
        reservation.status = ReservationStatus.CANCELLED
        logger.info("reservation_cancelled", reservation_id=reservation_id)
        return reservation

    def check_conflicts(
        self,
        start_time: float,
        end_time: float,
        resources: list[ReservationResource],
    ) -> list[ReservationConflict]:
        conflicts: list[ReservationConflict] = []
        requested_types = {r.resource_type for r in resources}

        for res in self._reservations.values():
            if res.status not in (ReservationStatus.APPROVED, ReservationStatus.ACTIVE):
                continue
            # Check time overlap
            if res.start_time >= end_time or res.end_time <= start_time:
                continue
            # Check resource type overlap
            existing_types = {r.resource_type for r in res.resources}
            overlap = requested_types & existing_types
            for rtype in overlap:
                conflicts.append(
                    ReservationConflict(
                        reservation_id="new",
                        conflicting_id=res.id,
                        resource_type=rtype,
                        message=(
                            f"Overlapping {rtype} reservation with '{res.name}' "
                            f"({res.start_time:.0f}-{res.end_time:.0f})"
                        ),
                    )
                )
        return conflicts

    def list_reservations(
        self,
        status: ReservationStatus | None = None,
    ) -> list[CapacityReservation]:
        reservations = list(self._reservations.values())
        if status:
            reservations = [r for r in reservations if r.status == status]
        return reservations

    def get_reservation(
        self,
        reservation_id: str,
    ) -> CapacityReservation | None:
        return self._reservations.get(reservation_id)

    def get_utilization(self) -> dict[str, Any]:
        utilization: dict[str, float] = defaultdict(float)
        unit_map: dict[str, str] = {}

        for res in self._reservations.values():
            if res.status != ReservationStatus.ACTIVE:
                continue
            for resource in res.resources:
                utilization[resource.resource_type] += resource.amount
                unit_map[resource.resource_type] = resource.unit

        return {
            "active_resources": {
                rtype: {"total_amount": amount, "unit": unit_map.get(rtype, "")}
                for rtype, amount in utilization.items()
            },
            "active_reservations": sum(
                1 for r in self._reservations.values() if r.status == ReservationStatus.ACTIVE
            ),
        }

    def get_stats(self) -> dict[str, Any]:
        status_counts: dict[str, int] = defaultdict(int)
        for res in self._reservations.values():
            status_counts[res.status] += 1
        return {
            "total_reservations": len(self._reservations),
            "pending": status_counts.get(ReservationStatus.PENDING, 0),
            "approved": status_counts.get(ReservationStatus.APPROVED, 0),
            "active": status_counts.get(ReservationStatus.ACTIVE, 0),
            "expired": status_counts.get(ReservationStatus.EXPIRED, 0),
            "cancelled": status_counts.get(ReservationStatus.CANCELLED, 0),
        }
