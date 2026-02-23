"""On-call schedule management.

Native rotation scheduling with timezone support, overrides,
and shift planning for incident response teams.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class RotationType(enum.StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


class ScheduleStatus(enum.StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


# -- Models --------------------------------------------------------------------


class OnCallShift(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    user: str
    start_time: float
    end_time: float
    is_override: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class OnCallOverride(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    schedule_id: str
    user: str
    start_time: float
    end_time: float
    reason: str = ""
    created_by: str = ""
    created_at: float = Field(default_factory=time.time)


class OnCallRotation(BaseModel):
    rotation_type: RotationType = RotationType.WEEKLY
    users: list[str] = Field(default_factory=list)
    rotation_interval_hours: float = 168.0  # 1 week
    handoff_time_hour: int = 9  # 9 AM


class OnCallSchedule(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    description: str = ""
    team: str = ""
    timezone: str = "UTC"
    rotation: OnCallRotation = Field(default_factory=OnCallRotation)
    overrides: list[OnCallOverride] = Field(default_factory=list)
    status: ScheduleStatus = ScheduleStatus.ACTIVE
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


# -- Manager -------------------------------------------------------------------


class OnCallScheduleManager:
    """Manage on-call schedules and rotations.

    Parameters
    ----------
    default_rotation:
        Default rotation type for new schedules.
    max_schedules:
        Maximum schedules to store.
    """

    def __init__(
        self,
        default_rotation: str = "weekly",
        max_schedules: int = 100,
    ) -> None:
        self._schedules: dict[str, OnCallSchedule] = {}
        self._default_rotation = default_rotation
        self._max_schedules = max_schedules

    def create_schedule(
        self,
        name: str,
        users: list[str],
        team: str = "",
        timezone: str = "UTC",
        rotation_type: RotationType | None = None,
        rotation_interval_hours: float | None = None,
        handoff_time_hour: int = 9,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> OnCallSchedule:
        if len(self._schedules) >= self._max_schedules:
            raise ValueError(f"Maximum schedules limit reached: {self._max_schedules}")
        if not users:
            raise ValueError("At least one user is required for a schedule")

        rtype = rotation_type or RotationType(self._default_rotation)
        interval = rotation_interval_hours
        if interval is None:
            interval = 24.0 if rtype == RotationType.DAILY else 168.0

        rotation = OnCallRotation(
            rotation_type=rtype,
            users=users,
            rotation_interval_hours=interval,
            handoff_time_hour=handoff_time_hour,
        )
        schedule = OnCallSchedule(
            name=name,
            description=description,
            team=team,
            timezone=timezone,
            rotation=rotation,
            metadata=metadata or {},
        )
        self._schedules[schedule.id] = schedule
        logger.info("oncall_schedule_created", schedule_id=schedule.id, name=name)
        return schedule

    def get_schedule(self, schedule_id: str) -> OnCallSchedule | None:
        return self._schedules.get(schedule_id)

    def list_schedules(
        self,
        status: ScheduleStatus | None = None,
        team: str | None = None,
    ) -> list[OnCallSchedule]:
        schedules = list(self._schedules.values())
        if status:
            schedules = [s for s in schedules if s.status == status]
        if team:
            schedules = [s for s in schedules if s.team == team]
        return schedules

    def get_current_oncall(self, schedule_id: str) -> str | None:
        schedule = self._schedules.get(schedule_id)
        if schedule is None or schedule.status != ScheduleStatus.ACTIVE:
            return None
        now = time.time()

        # Check overrides first
        for override in schedule.overrides:
            if override.start_time <= now <= override.end_time:
                return override.user

        # Calculate rotation position
        users = schedule.rotation.users
        if not users:
            return None
        interval_seconds = schedule.rotation.rotation_interval_hours * 3600
        if interval_seconds <= 0:
            return users[0]
        elapsed = now - schedule.created_at
        rotation_index = int(elapsed / interval_seconds) % len(users)
        return users[rotation_index]

    def add_override(
        self,
        schedule_id: str,
        user: str,
        start_time: float,
        end_time: float,
        reason: str = "",
        created_by: str = "",
    ) -> OnCallOverride | None:
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            return None
        if end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        override = OnCallOverride(
            schedule_id=schedule_id,
            user=user,
            start_time=start_time,
            end_time=end_time,
            reason=reason,
            created_by=created_by,
        )
        schedule.overrides.append(override)
        schedule.updated_at = time.time()
        logger.info("oncall_override_added", schedule_id=schedule_id, user=user)
        return override

    def get_schedule_for_range(
        self,
        schedule_id: str,
        start_time: float,
        end_time: float,
    ) -> list[OnCallShift]:
        schedule = self._schedules.get(schedule_id)
        if schedule is None:
            return []
        users = schedule.rotation.users
        if not users:
            return []
        interval = schedule.rotation.rotation_interval_hours * 3600
        if interval <= 0:
            return [OnCallShift(user=users[0], start_time=start_time, end_time=end_time)]

        shifts: list[OnCallShift] = []
        current = start_time
        while current < end_time:
            elapsed = current - schedule.created_at
            idx = int(elapsed / interval) % len(users)
            shift_end = min(current + interval, end_time)

            # Check for overrides
            user = users[idx]
            is_override = False
            for override in schedule.overrides:
                if override.start_time <= current < override.end_time:
                    user = override.user
                    is_override = True
                    break
            shifts.append(
                OnCallShift(
                    user=user,
                    start_time=current,
                    end_time=shift_end,
                    is_override=is_override,
                )
            )
            current = shift_end
        return shifts

    def get_stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        total_users = set()
        for s in self._schedules.values():
            by_status[s.status.value] = by_status.get(s.status.value, 0) + 1
            total_users.update(s.rotation.users)
        return {
            "total_schedules": len(self._schedules),
            "by_status": by_status,
            "total_users": len(total_users),
        }
