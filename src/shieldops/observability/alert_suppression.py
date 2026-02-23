"""Alert suppression and maintenance windows.

Suppresses alerts during scheduled maintenance windows or via custom rules
to reduce noise during known operational periods.
"""

from __future__ import annotations

import enum
import re
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class SuppressionRuleStatus(enum.StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    DISABLED = "disabled"


class WindowStatus(enum.StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# -- Models --------------------------------------------------------------------


class SuppressionRule(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    description: str = ""
    match_labels: dict[str, str] = Field(default_factory=dict)
    match_pattern: str = ""
    status: SuppressionRuleStatus = SuppressionRuleStatus.ACTIVE
    expires_at: float | None = None
    created_at: float = Field(default_factory=time.time)
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class MaintenanceWindow(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    description: str = ""
    services: list[str] = Field(default_factory=list)
    start_time: float
    end_time: float
    status: WindowStatus = WindowStatus.SCHEDULED
    created_by: str = ""
    suppress_labels: dict[str, str] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SuppressionMatch(BaseModel):
    suppressed: bool
    reason: str = ""
    rule_id: str = ""
    window_id: str = ""


# -- Engine --------------------------------------------------------------------


class AlertSuppressionEngine:
    """Manage alert suppression rules and maintenance windows.

    Parameters
    ----------
    max_rules:
        Maximum suppression rules to store.
    max_window_duration_hours:
        Maximum allowed maintenance window duration.
    """

    def __init__(
        self,
        max_rules: int = 500,
        max_window_duration_hours: int = 24,
    ) -> None:
        self._rules: dict[str, SuppressionRule] = {}
        self._windows: dict[str, MaintenanceWindow] = {}
        self._max_rules = max_rules
        self._max_window_hours = max_window_duration_hours

    def add_rule(
        self,
        name: str,
        match_labels: dict[str, str] | None = None,
        match_pattern: str = "",
        description: str = "",
        expires_at: float | None = None,
        created_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SuppressionRule:
        if len(self._rules) >= self._max_rules:
            raise ValueError(f"Maximum rules limit reached: {self._max_rules}")
        rule = SuppressionRule(
            name=name,
            match_labels=match_labels or {},
            match_pattern=match_pattern,
            description=description,
            expires_at=expires_at,
            created_by=created_by,
            metadata=metadata or {},
        )
        self._rules[rule.id] = rule
        logger.info("suppression_rule_added", rule_id=rule.id, name=name)
        return rule

    def remove_rule(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    def list_rules(
        self,
        status: SuppressionRuleStatus | None = None,
    ) -> list[SuppressionRule]:
        rules = list(self._rules.values())
        if status:
            rules = [r for r in rules if r.status == status]
        return rules

    def schedule_window(
        self,
        name: str,
        start_time: float,
        end_time: float,
        services: list[str] | None = None,
        description: str = "",
        created_by: str = "",
        suppress_labels: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MaintenanceWindow:
        duration_hours = (end_time - start_time) / 3600
        if duration_hours > self._max_window_hours:
            raise ValueError(
                f"Window duration {duration_hours:.1f}h exceeds max {self._max_window_hours}h"
            )
        if end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        window = MaintenanceWindow(
            name=name,
            start_time=start_time,
            end_time=end_time,
            services=services or [],
            description=description,
            created_by=created_by,
            suppress_labels=suppress_labels or {},
            metadata=metadata or {},
        )
        self._windows[window.id] = window
        logger.info("maintenance_window_scheduled", window_id=window.id, name=name)
        return window

    def cancel_window(self, window_id: str) -> MaintenanceWindow | None:
        window = self._windows.get(window_id)
        if window is None:
            return None
        window.status = WindowStatus.CANCELLED
        return window

    def get_active_windows(self) -> list[MaintenanceWindow]:
        now = time.time()
        active: list[MaintenanceWindow] = []
        for w in self._windows.values():
            if w.status == WindowStatus.CANCELLED:
                continue
            if w.start_time <= now <= w.end_time:
                if w.status != WindowStatus.ACTIVE:
                    w.status = WindowStatus.ACTIVE
                active.append(w)
            elif now > w.end_time and w.status != WindowStatus.COMPLETED:
                w.status = WindowStatus.COMPLETED
        return active

    def should_suppress(
        self,
        alert_name: str = "",
        labels: dict[str, str] | None = None,
        service: str = "",
    ) -> SuppressionMatch:
        now = time.time()
        alert_labels = labels or {}

        # Check rules
        for rule in self._rules.values():
            if rule.status != SuppressionRuleStatus.ACTIVE:
                continue
            if rule.expires_at and now > rule.expires_at:
                rule.status = SuppressionRuleStatus.EXPIRED
                continue
            # Label matching
            if rule.match_labels and all(
                alert_labels.get(k) == v for k, v in rule.match_labels.items()
            ):
                return SuppressionMatch(
                    suppressed=True,
                    reason=f"Matched rule: {rule.name}",
                    rule_id=rule.id,
                )
            # Pattern matching
            if rule.match_pattern and alert_name and re.search(rule.match_pattern, alert_name):
                return SuppressionMatch(
                    suppressed=True,
                    reason=f"Pattern match: {rule.name}",
                    rule_id=rule.id,
                )

        # Check maintenance windows
        for window in self._windows.values():
            if window.status == WindowStatus.CANCELLED:
                continue
            if window.start_time <= now <= window.end_time:
                if service and window.services and service in window.services:
                    return SuppressionMatch(
                        suppressed=True,
                        reason=f"Maintenance window: {window.name}",
                        window_id=window.id,
                    )
                if window.suppress_labels and all(
                    alert_labels.get(k) == v for k, v in window.suppress_labels.items()
                ):
                    return SuppressionMatch(
                        suppressed=True,
                        reason=f"Maintenance window labels: {window.name}",
                        window_id=window.id,
                    )
                if not window.services and not window.suppress_labels:
                    return SuppressionMatch(
                        suppressed=True,
                        reason=f"Global maintenance window: {window.name}",
                        window_id=window.id,
                    )

        return SuppressionMatch(suppressed=False)

    def get_stats(self) -> dict[str, Any]:
        active_rules = sum(
            1 for r in self._rules.values() if r.status == SuppressionRuleStatus.ACTIVE
        )
        active_windows = len(self.get_active_windows())
        return {
            "total_rules": len(self._rules),
            "active_rules": active_rules,
            "total_windows": len(self._windows),
            "active_windows": active_windows,
        }
