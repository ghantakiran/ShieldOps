"""Tenant-aware sliding-window rate limiter (in-memory, no Redis)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any

import structlog

logger = structlog.get_logger()

# Default window size in seconds
_WINDOW_SECONDS = 60


class TenantRateLimiter:
    """Per-org sliding-window rate limiter backed by in-memory timestamps.

    Each call to :meth:`check_rate_limit` appends the current timestamp
    and prunes entries older than the window.  This gives a true
    sliding-window count without external dependencies.
    """

    def __init__(self, window_seconds: int = _WINDOW_SECONDS) -> None:
        self._window = window_seconds
        self._mu = threading.Lock()
        # org_id -> list of request timestamps
        self._requests: dict[str, list[float]] = defaultdict(list)
        # Default per-org limit (overridden via check_rate_limit)
        self._default_limit = 60

    # ── Core ─────────────────────────────────────────────────

    async def check_rate_limit(
        self,
        org_id: str,
        limit_override: int | None = None,
    ) -> tuple[bool, int]:
        """Check whether *org_id* is within its rate limit.

        Parameters
        ----------
        org_id:
            Tenant identifier.
        limit_override:
            If provided, uses this limit instead of the default.

        Returns
        -------
        tuple[bool, int]
            ``(allowed, remaining)`` where *allowed* is ``True`` when the
            request should proceed and *remaining* is the number of
            requests left in the current window.

        """
        limit = limit_override if limit_override is not None else self._default_limit
        now = time.monotonic()
        cutoff = now - self._window

        with self._mu:
            timestamps = self._requests[org_id]

            # Prune expired entries
            self._requests[org_id] = [ts for ts in timestamps if ts > cutoff]
            timestamps = self._requests[org_id]

            current_count = len(timestamps)

            if current_count >= limit:
                remaining = 0
                logger.debug(
                    "rate_limit_exceeded",
                    org_id=org_id,
                    limit=limit,
                    count=current_count,
                )
                return False, remaining

            # Record this request
            timestamps.append(now)
            remaining = limit - current_count - 1

        return True, remaining

    # ── Stats ────────────────────────────────────────────────

    def get_usage_stats(self, org_id: str) -> dict[str, Any]:
        """Return current-window usage statistics for *org_id*."""
        now = time.monotonic()
        cutoff = now - self._window

        with self._mu:
            timestamps = self._requests.get(org_id, [])
            active = [ts for ts in timestamps if ts > cutoff]

        return {
            "org_id": org_id,
            "window_seconds": self._window,
            "requests_in_window": len(active),
            "default_limit": self._default_limit,
        }

    def reset(self, org_id: str | None = None) -> None:
        """Clear tracked requests. Pass *org_id* to reset a single tenant."""
        with self._mu:
            if org_id is not None:
                self._requests.pop(org_id, None)
            else:
                self._requests.clear()
