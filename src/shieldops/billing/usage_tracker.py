"""Usage metering — records billable events, buffers, and flushes to Stripe.

The ``UsageTracker`` maintains a thread-safe in-memory buffer that is
flushed either every 60 seconds or when the buffer exceeds 100 events,
whichever comes first.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any

import structlog

from shieldops.billing.usage_models import (
    UsageAlert,
    UsageAlertType,
    UsageEvent,
    UsageEventType,
    UsageSummary,
)

logger = structlog.get_logger()

_FLUSH_INTERVAL_SECONDS = 60
_FLUSH_BUFFER_THRESHOLD = 100


class UsageTracker:
    """Records usage events in an in-memory buffer and flushes to Stripe.

    All public methods are async-safe; the internal buffer is protected
    by an ``asyncio.Lock``.
    """

    def __init__(
        self,
        stripe_service: Any | None = None,
        flush_interval: int = _FLUSH_INTERVAL_SECONDS,
        buffer_threshold: int = _FLUSH_BUFFER_THRESHOLD,
    ) -> None:
        self._stripe = stripe_service
        self._flush_interval = flush_interval
        self._buffer_threshold = buffer_threshold

        # org_id -> list of pending events
        self._buffer: dict[str, list[UsageEvent]] = {}
        # org_id -> list of all persisted events (history)
        self._history: dict[str, list[UsageEvent]] = {}
        # org_id -> plan tier name
        self._org_plans: dict[str, str] = {}
        # org_id -> included execution limit for current plan
        self._org_limits: dict[str, int] = {}

        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_periodic_flush(self) -> None:
        """Start the background flush loop."""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._periodic_flush())

    async def stop(self) -> None:
        """Cancel the periodic flush and drain remaining events."""
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task
        # Final drain
        async with self._lock:
            for org_id in list(self._buffer):
                await self._flush_buffer(org_id)

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    async def set_org_plan(
        self,
        org_id: str,
        plan: str,
        included_limit: int,
    ) -> None:
        """Register an org's plan and execution limit."""
        async with self._lock:
            self._org_plans[org_id] = plan
            self._org_limits[org_id] = included_limit

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def record_event(
        self,
        org_id: str,
        event_type: UsageEventType,
        quantity: int = 1,
        metadata: dict[str, str] | None = None,
    ) -> UsageEvent:
        """Record a billable usage event.

        The event is placed in an in-memory buffer.  When the buffer
        reaches ``buffer_threshold`` events the buffer is flushed
        automatically.

        Args:
            org_id: Organisation identifier.
            event_type: The type of billable event.
            quantity: Number of units consumed (default 1).
            metadata: Optional key/value metadata for the event.

        Returns:
            The recorded ``UsageEvent``.
        """
        event = UsageEvent(
            org_id=org_id,
            event_type=event_type,
            quantity=quantity,
            metadata=metadata or {},
        )

        async with self._lock:
            self._buffer.setdefault(org_id, []).append(event)
            self._history.setdefault(org_id, []).append(event)
            buf_len = len(self._buffer[org_id])

        logger.debug(
            "usage_event_recorded",
            org_id=org_id,
            event_type=event_type.value,
            quantity=quantity,
            buffer_size=buf_len,
        )

        if buf_len >= self._buffer_threshold:
            await self.flush_to_stripe(org_id)

        return event

    async def get_usage_summary(
        self,
        org_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> UsageSummary:
        """Return aggregated usage for an org within a date range.

        Args:
            org_id: Organisation identifier.
            period_start: Start of the billing period (inclusive).
            period_end: End of the billing period (exclusive).

        Returns:
            A ``UsageSummary`` with per-type counts and totals.
        """
        async with self._lock:
            events = self._history.get(org_id, [])

        events_by_type: dict[UsageEventType, int] = {}
        total = 0
        for ev in events:
            if period_start <= ev.timestamp < period_end:
                events_by_type[ev.event_type] = events_by_type.get(ev.event_type, 0) + ev.quantity
                total += ev.quantity

        return UsageSummary(
            org_id=org_id,
            period_start=period_start,
            period_end=period_end,
            events_by_type=events_by_type,
            total_events=total,
        )

    async def get_current_period_usage(self, org_id: str) -> UsageSummary:
        """Return usage for the current calendar-month billing period.

        Uses the first day of the current month as ``period_start``
        and the current timestamp as ``period_end``.
        """
        now = datetime.now(UTC)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return await self.get_usage_summary(org_id, period_start, now)

    async def check_usage_limits(
        self,
        org_id: str,
    ) -> UsageAlert | None:
        """Check whether org usage is approaching or exceeding limits.

        Thresholds:
          - 80 %  -> ``approaching_limit``
          - 100 % -> ``exceeded_limit``
          - 150 % -> ``anomalous_usage``

        Returns:
            A ``UsageAlert`` if a threshold is crossed, else ``None``.
        """
        summary = await self.get_current_period_usage(org_id)
        limit = self._org_limits.get(org_id, 0)

        if limit <= 0:
            # Unlimited plan or unregistered — no alert
            return None

        pct = (summary.total_events / limit) * 100

        if pct >= 150:
            alert_type = UsageAlertType.anomalous_usage
        elif pct >= 100:
            alert_type = UsageAlertType.exceeded_limit
        elif pct >= 80:
            alert_type = UsageAlertType.approaching_limit
        else:
            return None

        alert = UsageAlert(
            org_id=org_id,
            alert_type=alert_type,
            threshold_pct=round(pct, 1),
            current_usage=summary.total_events,
            limit=limit,
            message=(
                f"Organisation {org_id} has used {summary.total_events}"
                f" of {limit} included executions ({pct:.0f}%)."
            ),
        )

        logger.warning(
            "usage_limit_alert",
            org_id=org_id,
            alert_type=alert_type.value,
            pct=round(pct, 1),
        )
        return alert

    async def flush_to_stripe(self, org_id: str) -> int:
        """Report buffered usage to Stripe via the usage records API.

        Args:
            org_id: Organisation whose buffer should be flushed.

        Returns:
            Number of events flushed.
        """
        async with self._lock:
            events = self._buffer.pop(org_id, [])

        if not events:
            return 0

        total_quantity = sum(ev.quantity for ev in events)

        if self._stripe is not None:
            try:
                await self._stripe.report_usage(
                    org_id=org_id,
                    quantity=total_quantity,
                    timestamp=int(datetime.now(UTC).timestamp()),
                )
                logger.info(
                    "usage_flushed_to_stripe",
                    org_id=org_id,
                    events=len(events),
                    total_quantity=total_quantity,
                )
            except Exception:
                logger.exception(
                    "usage_flush_to_stripe_failed",
                    org_id=org_id,
                    events=len(events),
                )
                # Re-buffer on failure so data is not lost
                async with self._lock:
                    existing = self._buffer.get(org_id, [])
                    self._buffer[org_id] = events + existing
                return 0

        # Mark events as reported
        for ev in events:
            ev.reported_to_stripe = True

        return len(events)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _flush_buffer(self, org_id: str) -> None:
        """Flush a single org's buffer (caller holds the lock)."""
        events = self._buffer.pop(org_id, [])
        if not events:
            return
        for ev in events:
            ev.reported_to_stripe = True

    async def _periodic_flush(self) -> None:
        """Background task that flushes all org buffers periodically."""
        while True:
            await asyncio.sleep(self._flush_interval)
            async with self._lock:
                org_ids = list(self._buffer.keys())
            for org_id in org_ids:
                await self.flush_to_stripe(org_id)
            logger.debug(
                "usage_periodic_flush_complete",
                orgs_flushed=len(org_ids),
            )
