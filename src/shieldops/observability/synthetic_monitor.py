"""Synthetic Monitor Manager — manages synthetic monitoring probes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MonitorType(StrEnum):
    HTTP = "http"
    API = "api"
    BROWSER = "browser"
    TCP = "tcp"
    DNS = "dns"
    SSL_CERT = "ssl_cert"


class MonitorStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    FAILING = "failing"
    DISABLED = "disabled"


# --- Models ---


class SyntheticMonitor(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    monitor_type: MonitorType
    target_url: str
    interval_seconds: int = 60
    timeout_seconds: int = 30
    expected_status_code: int = 200
    regions: list[str] = Field(default_factory=list)
    status: MonitorStatus = MonitorStatus.ACTIVE
    consecutive_failures: int = 0
    last_check_at: float | None = None
    last_success_at: float | None = None
    owner: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class CheckResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    monitor_id: str
    success: bool
    response_time_ms: float = 0.0
    status_code: int | None = None
    region: str = ""
    error_message: str = ""
    checked_at: float = Field(default_factory=time.time)


# --- Manager ---


class SyntheticMonitorManager:
    """Manages synthetic monitoring probes (HTTP checks, API tests, browser simulations)."""

    def __init__(
        self,
        max_monitors: int = 500,
        max_results: int = 100000,
        failure_threshold: int = 3,
    ) -> None:
        self.max_monitors = max_monitors
        self.max_results = max_results
        self.failure_threshold = failure_threshold
        self._monitors: dict[str, SyntheticMonitor] = {}
        self._results: list[CheckResult] = []
        logger.info(
            "synthetic_monitor_manager.initialized",
            max_monitors=max_monitors,
            max_results=max_results,
            failure_threshold=failure_threshold,
        )

    def create_monitor(
        self, name: str, monitor_type: MonitorType, target_url: str, **kw: Any
    ) -> SyntheticMonitor:
        """Create a new synthetic monitor."""
        if len(self._monitors) >= self.max_monitors:
            raise ValueError(f"Max monitors limit reached ({self.max_monitors})")
        monitor = SyntheticMonitor(
            name=name,
            monitor_type=monitor_type,
            target_url=target_url,
            **kw,
        )
        self._monitors[monitor.id] = monitor
        logger.info(
            "synthetic_monitor_manager.monitor_created",
            monitor_id=monitor.id,
            name=name,
            monitor_type=monitor_type,
            target_url=target_url,
        )
        return monitor

    def record_check(self, monitor_id: str, success: bool, **kw: Any) -> CheckResult:
        """Record a check result for a monitor.

        Updates the monitor's last_check_at and consecutive_failures.
        If consecutive_failures >= failure_threshold, sets status to FAILING.
        On success, resets consecutive_failures, updates last_success_at, sets status to ACTIVE.
        """
        monitor = self._monitors.get(monitor_id)
        if monitor is None:
            raise ValueError(f"Monitor not found: {monitor_id}")

        result = CheckResult(monitor_id=monitor_id, success=success, **kw)
        monitor.last_check_at = result.checked_at

        if success:
            monitor.consecutive_failures = 0
            monitor.last_success_at = result.checked_at
            if monitor.status == MonitorStatus.FAILING:
                monitor.status = MonitorStatus.ACTIVE
        else:
            monitor.consecutive_failures += 1
            if monitor.consecutive_failures >= self.failure_threshold:
                monitor.status = MonitorStatus.FAILING

        self._results.append(result)
        if len(self._results) > self.max_results:
            self._results = self._results[-self.max_results :]

        logger.info(
            "synthetic_monitor_manager.check_recorded",
            result_id=result.id,
            monitor_id=monitor_id,
            success=success,
            consecutive_failures=monitor.consecutive_failures,
        )
        return result

    def get_monitor(self, monitor_id: str) -> SyntheticMonitor | None:
        """Get a monitor by ID."""
        return self._monitors.get(monitor_id)

    def list_monitors(
        self,
        status: MonitorStatus | None = None,
        monitor_type: MonitorType | None = None,
    ) -> list[SyntheticMonitor]:
        """List monitors with optional filters."""
        results = list(self._monitors.values())
        if status is not None:
            results = [m for m in results if m.status == status]
        if monitor_type is not None:
            results = [m for m in results if m.monitor_type == monitor_type]
        return results

    def pause_monitor(self, monitor_id: str) -> SyntheticMonitor | None:
        """Pause a monitor."""
        monitor = self._monitors.get(monitor_id)
        if monitor is None:
            return None
        monitor.status = MonitorStatus.PAUSED
        logger.info(
            "synthetic_monitor_manager.monitor_paused",
            monitor_id=monitor_id,
        )
        return monitor

    def resume_monitor(self, monitor_id: str) -> SyntheticMonitor | None:
        """Resume a paused monitor."""
        monitor = self._monitors.get(monitor_id)
        if monitor is None:
            return None
        monitor.status = MonitorStatus.ACTIVE
        monitor.consecutive_failures = 0
        logger.info(
            "synthetic_monitor_manager.monitor_resumed",
            monitor_id=monitor_id,
        )
        return monitor

    def delete_monitor(self, monitor_id: str) -> bool:
        """Delete a monitor."""
        if monitor_id in self._monitors:
            del self._monitors[monitor_id]
            logger.info(
                "synthetic_monitor_manager.monitor_deleted",
                monitor_id=monitor_id,
            )
            return True
        return False

    def get_check_history(
        self, monitor_id: str | None = None, limit: int = 100
    ) -> list[CheckResult]:
        """Get check results, newest first."""
        results = list(self._results)
        if monitor_id is not None:
            results = [r for r in results if r.monitor_id == monitor_id]
        results.sort(key=lambda r: r.checked_at, reverse=True)
        return results[:limit]

    def get_availability(self, monitor_id: str) -> dict[str, Any]:
        """Get availability metrics for a monitor."""
        checks = [r for r in self._results if r.monitor_id == monitor_id]
        total = len(checks)
        if total == 0:
            return {
                "total_checks": 0,
                "successful": 0,
                "failed": 0,
                "availability_pct": 0.0,
                "avg_response_time_ms": 0.0,
            }
        successful = sum(1 for c in checks if c.success)
        failed = total - successful
        avg_response = sum(c.response_time_ms for c in checks) / total if total > 0 else 0.0
        return {
            "total_checks": total,
            "successful": successful,
            "failed": failed,
            "availability_pct": (successful / total) * 100.0,
            "avg_response_time_ms": avg_response,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get summary statistics."""
        monitors = list(self._monitors.values())
        active = sum(1 for m in monitors if m.status == MonitorStatus.ACTIVE)
        paused = sum(1 for m in monitors if m.status == MonitorStatus.PAUSED)
        failing = sum(1 for m in monitors if m.status == MonitorStatus.FAILING)
        total_checks = len(self._results)
        successful_checks = sum(1 for r in self._results if r.success)
        overall_avail = (successful_checks / total_checks) * 100.0 if total_checks > 0 else 0.0
        return {
            "total_monitors": len(monitors),
            "active": active,
            "paused": paused,
            "failing": failing,
            "total_checks": total_checks,
            "overall_availability_pct": overall_avail,
        }
