"""Maintenance Window Manager — schedules and manages maintenance windows."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WindowStatus(StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXTENDED = "extended"


class WindowType(StrEnum):
    PLANNED = "planned"
    EMERGENCY = "emergency"
    RECURRING = "recurring"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class MaintenanceWindow(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    services: list[str] = Field(default_factory=list)
    window_type: WindowType = Field(default=WindowType.PLANNED)
    status: WindowStatus = Field(default=WindowStatus.SCHEDULED)
    start_time: float
    end_time: float
    owner: str = Field(default="")
    description: str = Field(default="")
    notifications_sent: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class WindowConflict(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    window_a_id: str
    window_b_id: str
    overlapping_services: list[str] = Field(default_factory=list)
    overlap_start: float
    overlap_end: float
    detected_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class MaintenanceWindowManager:
    """Schedules and manages maintenance windows with conflict detection."""

    def __init__(
        self,
        max_windows: int = 2000,
        max_duration_hours: float = 48,
    ) -> None:
        self.max_windows = max_windows
        self.max_duration_hours = max_duration_hours
        self._windows: dict[str, MaintenanceWindow] = {}
        self._conflicts: list[WindowConflict] = []
        logger.info(
            "maintenance_window_manager.initialized",
            max_windows=max_windows,
            max_duration_hours=max_duration_hours,
        )

    # -- helpers -------------------------------------------------------------

    def _validate_duration(self, start_time: float, end_time: float) -> None:
        if end_time <= start_time:
            raise ValueError("end_time must be greater than start_time")
        duration_hours = (end_time - start_time) / 3600
        if duration_hours > self.max_duration_hours:
            raise ValueError(
                f"Window duration {duration_hours:.1f}h exceeds maximum {self.max_duration_hours}h"
            )

    # -- public API ----------------------------------------------------------

    def create_window(
        self,
        title: str,
        services: list[str],
        start_time: float,
        end_time: float,
        **kw: Any,
    ) -> MaintenanceWindow:
        """Create a new maintenance window."""
        if len(self._windows) >= self.max_windows:
            raise ValueError(f"Maximum windows ({self.max_windows}) exceeded")
        self._validate_duration(start_time, end_time)

        window = MaintenanceWindow(
            title=title,
            services=services,
            start_time=start_time,
            end_time=end_time,
            **kw,
        )
        self._windows[window.id] = window
        logger.info(
            "maintenance_window.created",
            window_id=window.id,
            title=title,
            services=services,
        )
        return window

    def activate_window(self, window_id: str) -> MaintenanceWindow | None:
        """Set a window's status to ACTIVE."""
        window = self._windows.get(window_id)
        if window is None:
            return None
        window.status = WindowStatus.ACTIVE
        logger.info("maintenance_window.activated", window_id=window_id)
        return window

    def complete_window(self, window_id: str) -> MaintenanceWindow | None:
        """Set a window's status to COMPLETED."""
        window = self._windows.get(window_id)
        if window is None:
            return None
        window.status = WindowStatus.COMPLETED
        logger.info("maintenance_window.completed", window_id=window_id)
        return window

    def cancel_window(self, window_id: str) -> MaintenanceWindow | None:
        """Set a window's status to CANCELLED."""
        window = self._windows.get(window_id)
        if window is None:
            return None
        window.status = WindowStatus.CANCELLED
        logger.info("maintenance_window.cancelled", window_id=window_id)
        return window

    def extend_window(self, window_id: str, new_end_time: float) -> MaintenanceWindow | None:
        """Extend a window's end time and set status to EXTENDED."""
        window = self._windows.get(window_id)
        if window is None:
            return None
        # Validate new duration from original start
        duration_hours = (new_end_time - window.start_time) / 3600
        if duration_hours > self.max_duration_hours:
            raise ValueError(
                f"Extended duration {duration_hours:.1f}h exceeds "
                f"maximum {self.max_duration_hours}h"
            )
        window.end_time = new_end_time
        window.status = WindowStatus.EXTENDED
        logger.info(
            "maintenance_window.extended",
            window_id=window_id,
            new_end_time=new_end_time,
        )
        return window

    def check_conflicts(self, window_id: str | None = None) -> list[WindowConflict]:
        """Find overlapping windows for the same services."""
        # Determine which windows to check
        active_statuses = {WindowStatus.SCHEDULED, WindowStatus.ACTIVE, WindowStatus.EXTENDED}

        if window_id is not None:
            target = self._windows.get(window_id)
            if target is None:
                return []
            targets = [target]
            others = [
                w
                for w in self._windows.values()
                if w.id != window_id and w.status in active_statuses
            ]
        else:
            candidates = [w for w in self._windows.values() if w.status in active_statuses]
            targets = candidates
            others = candidates

        conflicts: list[WindowConflict] = []
        seen_pairs: set[tuple[str, str]] = set()

        for t in targets:
            for o in others:
                if t.id == o.id:
                    continue
                sorted_ids = sorted([t.id, o.id])
                pair = (sorted_ids[0], sorted_ids[1])
                if pair in seen_pairs:
                    continue

                # Check time overlap
                overlap_start = max(t.start_time, o.start_time)
                overlap_end = min(t.end_time, o.end_time)
                if overlap_start >= overlap_end:
                    continue

                # Check service overlap
                overlapping = list(set(t.services) & set(o.services))
                if not overlapping:
                    continue

                seen_pairs.add(pair)
                conflict = WindowConflict(
                    window_a_id=t.id,
                    window_b_id=o.id,
                    overlapping_services=overlapping,
                    overlap_start=overlap_start,
                    overlap_end=overlap_end,
                )
                conflicts.append(conflict)
                self._conflicts.append(conflict)
                logger.warning(
                    "maintenance_window.conflict_detected",
                    window_a=t.id,
                    window_b=o.id,
                    overlapping_services=overlapping,
                )

        return conflicts

    def get_window(self, window_id: str) -> MaintenanceWindow | None:
        """Return a window by ID."""
        return self._windows.get(window_id)

    def list_windows(
        self,
        status: WindowStatus | None = None,
        service: str | None = None,
    ) -> list[MaintenanceWindow]:
        """List windows, optionally filtered by status or service."""
        result = list(self._windows.values())
        if status is not None:
            result = [w for w in result if w.status == status]
        if service is not None:
            result = [w for w in result if service in w.services]
        return result

    def get_active_windows(self) -> list[MaintenanceWindow]:
        """Return all currently active maintenance windows."""
        return self.list_windows(status=WindowStatus.ACTIVE)

    def notify_window(self, window_id: str, channel: str) -> MaintenanceWindow | None:
        """Record that a notification was sent for a window."""
        window = self._windows.get(window_id)
        if window is None:
            return None
        window.notifications_sent.append(channel)
        logger.info(
            "maintenance_window.notified",
            window_id=window_id,
            channel=channel,
        )
        return window

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        windows = list(self._windows.values())

        by_status: dict[str, int] = {}
        for w in windows:
            by_status[w.status] = by_status.get(w.status, 0) + 1

        by_type: dict[str, int] = {}
        for w in windows:
            by_type[w.window_type] = by_type.get(w.window_type, 0) + 1

        active_count = sum(1 for w in windows if w.status == WindowStatus.ACTIVE)

        durations = [(w.end_time - w.start_time) / 3600 for w in windows]
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0

        return {
            "total_windows": len(windows),
            "by_status": by_status,
            "by_type": by_type,
            "active_count": active_count,
            "total_conflicts": len(self._conflicts),
            "avg_duration_hours": avg_duration,
        }
