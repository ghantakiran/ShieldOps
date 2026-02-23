"""Deployment freeze window management for change control.

Manages deployment freeze windows that prevent changes during sensitive
periods such as holidays, audits, or major events, with support for
scoped exceptions.
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


class FreezeStatus(enum.StrEnum):
    ACTIVE = "active"
    SCHEDULED = "scheduled"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class FreezeScope(enum.StrEnum):
    ALL = "all"
    PRODUCTION = "production"
    STAGING = "staging"
    CUSTOM = "custom"


# -- Models --------------------------------------------------------------------


class FreezeWindow(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    reason: str = ""
    scope: FreezeScope = FreezeScope.ALL
    environments: list[str] = Field(default_factory=list)
    start_time: float
    end_time: float
    status: FreezeStatus = FreezeStatus.SCHEDULED
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class FreezeException(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    freeze_id: str
    service: str
    reason: str
    approved_by: str = ""
    created_at: float = Field(default_factory=time.time)


class FreezeCheckResult(BaseModel):
    frozen: bool
    reason: str = ""
    freeze_id: str = ""
    exception_id: str = ""


# -- Manager -------------------------------------------------------------------


class DeploymentFreezeManager:
    """Manage deployment freeze windows and exceptions.

    Parameters
    ----------
    max_windows:
        Maximum freeze windows to store.
    max_duration_days:
        Maximum allowed freeze window duration in days.
    """

    def __init__(
        self,
        max_windows: int = 200,
        max_duration_days: int = 30,
    ) -> None:
        self._freezes: dict[str, FreezeWindow] = {}
        self._exceptions: dict[str, FreezeException] = {}
        self._max_windows = max_windows
        self._max_duration_days = max_duration_days

    def create_freeze(
        self,
        name: str,
        start_time: float,
        end_time: float,
        scope: FreezeScope = FreezeScope.ALL,
        environments: list[str] | None = None,
        reason: str = "",
        created_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> FreezeWindow:
        if end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        duration_days = (end_time - start_time) / 86400
        if duration_days > self._max_duration_days:
            raise ValueError(
                f"Freeze duration {duration_days:.1f}d exceeds max {self._max_duration_days}d"
            )
        if len(self._freezes) >= self._max_windows:
            raise ValueError(f"Maximum freeze windows limit reached: {self._max_windows}")
        freeze = FreezeWindow(
            name=name,
            start_time=start_time,
            end_time=end_time,
            scope=scope,
            environments=environments or [],
            reason=reason,
            created_by=created_by,
            metadata=metadata or {},
        )
        self._freezes[freeze.id] = freeze
        logger.info("freeze_window_created", freeze_id=freeze.id, name=name)
        return freeze

    def cancel_freeze(self, freeze_id: str) -> FreezeWindow | None:
        freeze = self._freezes.get(freeze_id)
        if freeze is None:
            return None
        freeze.status = FreezeStatus.CANCELLED
        logger.info("freeze_window_cancelled", freeze_id=freeze_id)
        return freeze

    def check_frozen(
        self,
        environment: str = "production",
        service: str = "",
    ) -> FreezeCheckResult:
        now = time.time()
        for freeze in self._freezes.values():
            if freeze.status == FreezeStatus.CANCELLED:
                continue
            if freeze.status == FreezeStatus.EXPIRED:
                continue
            if now > freeze.end_time:
                freeze.status = FreezeStatus.EXPIRED
                continue
            if not (freeze.start_time <= now <= freeze.end_time):
                continue
            # Update status to active if within window
            if freeze.status == FreezeStatus.SCHEDULED:
                freeze.status = FreezeStatus.ACTIVE
            # Check scope matching
            scope_match = False
            if (
                freeze.scope == FreezeScope.ALL
                or (freeze.scope == FreezeScope.PRODUCTION and environment == "production")
                or (freeze.scope == FreezeScope.STAGING and environment == "staging")
            ):
                scope_match = True
            elif freeze.scope == FreezeScope.CUSTOM and freeze.environments:
                scope_match = environment in freeze.environments
            if not scope_match:
                continue
            # Check for exceptions
            if service:
                for exc in self._exceptions.values():
                    if exc.freeze_id == freeze.id and exc.service == service:
                        return FreezeCheckResult(
                            frozen=False,
                            reason=f"Exception granted: {exc.reason}",
                            freeze_id=freeze.id,
                            exception_id=exc.id,
                        )
            return FreezeCheckResult(
                frozen=True,
                reason=f"Deployment freeze active: {freeze.name}",
                freeze_id=freeze.id,
            )
        return FreezeCheckResult(frozen=False)

    def add_exception(
        self,
        freeze_id: str,
        service: str,
        reason: str,
        approved_by: str = "",
    ) -> FreezeException:
        if freeze_id not in self._freezes:
            raise ValueError(f"Freeze window not found: {freeze_id}")
        exception = FreezeException(
            freeze_id=freeze_id,
            service=service,
            reason=reason,
            approved_by=approved_by,
        )
        self._exceptions[exception.id] = exception
        logger.info(
            "freeze_exception_added",
            exception_id=exception.id,
            freeze_id=freeze_id,
            service=service,
        )
        return exception

    def list_freezes(
        self,
        status: FreezeStatus | None = None,
    ) -> list[FreezeWindow]:
        now = time.time()
        # Update expired status
        for freeze in self._freezes.values():
            if (
                freeze.status not in (FreezeStatus.CANCELLED, FreezeStatus.EXPIRED)
                and now > freeze.end_time
            ):
                freeze.status = FreezeStatus.EXPIRED
        freezes = list(self._freezes.values())
        if status:
            freezes = [f for f in freezes if f.status == status]
        return freezes

    def get_freeze(self, freeze_id: str) -> FreezeWindow | None:
        return self._freezes.get(freeze_id)

    def get_active_freezes(self) -> list[FreezeWindow]:
        now = time.time()
        active: list[FreezeWindow] = []
        for freeze in self._freezes.values():
            if freeze.status == FreezeStatus.CANCELLED:
                continue
            if freeze.status == FreezeStatus.EXPIRED:
                continue
            if now > freeze.end_time:
                freeze.status = FreezeStatus.EXPIRED
                continue
            if freeze.start_time <= now <= freeze.end_time:
                if freeze.status == FreezeStatus.SCHEDULED:
                    freeze.status = FreezeStatus.ACTIVE
                active.append(freeze)
        return active

    def get_stats(self) -> dict[str, Any]:
        active = len(self.get_active_freezes())
        scheduled = sum(1 for f in self._freezes.values() if f.status == FreezeStatus.SCHEDULED)
        expired = sum(1 for f in self._freezes.values() if f.status == FreezeStatus.EXPIRED)
        cancelled = sum(1 for f in self._freezes.values() if f.status == FreezeStatus.CANCELLED)
        return {
            "total_freezes": len(self._freezes),
            "active_freezes": active,
            "scheduled_freezes": scheduled,
            "expired_freezes": expired,
            "cancelled_freezes": cancelled,
            "total_exceptions": len(self._exceptions),
        }
