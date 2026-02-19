"""Lightweight Prometheus-compatible metrics middleware.

Tracks HTTP request counters, duration histograms, and in-progress gauges
without requiring the prometheus_client library. Exposes metrics in
Prometheus text exposition format via ``MetricsRegistry.collect()``.
"""

from __future__ import annotations

import re
import threading
import time
from typing import ClassVar

import structlog
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()

# ── Histogram bucket boundaries (seconds) ───────────────────────────
DEFAULT_BUCKETS: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

# ── Path-normalisation patterns ─────────────────────────────────────
# UUID v4 (standard 8-4-4-4-12 hex format)
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
# Hex strings >= 8 chars (short IDs, object IDs, etc.)
_HEX_ID_RE = re.compile(r"[0-9a-fA-F]{8,}")
# Pure numeric segments
_NUMERIC_RE = re.compile(r"^[0-9]+$")


def normalize_path(path: str) -> str:
    """Replace dynamic path segments with ``{id}`` placeholders.

    Handles UUIDs, hex identifiers, and numeric IDs so that
    ``/api/v1/investigations/abc123de`` becomes
    ``/api/v1/investigations/{id}``.
    """
    # Fast-path: skip known static paths
    if path in {"/health", "/ready", "/metrics"}:
        return path

    parts = path.split("/")
    normalized: list[str] = []
    for part in parts:
        if not part:
            normalized.append(part)
            continue
        if _UUID_RE.fullmatch(part) or _NUMERIC_RE.fullmatch(part) or _HEX_ID_RE.fullmatch(part):
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/".join(normalized)


# ── Metrics Registry (singleton) ────────────────────────────────────


class MetricsRegistry:
    """Thread-safe, dict-backed metrics store.

    Supports counters, histograms (with configurable buckets), and
    gauges.  The ``collect()`` method emits Prometheus text exposition
    format (version 0.0.4).
    """

    _instance: ClassVar[MetricsRegistry | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._mu = threading.Lock()
        self.counters: dict[str, int] = {}
        self.histograms: dict[str, list[tuple[float, int]]] = {}
        self._histogram_sums: dict[str, float] = {}
        self._histogram_counts: dict[str, int] = {}
        self.gauges: dict[str, int] = {}

    # ── Singleton access ────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> MetricsRegistry:
        """Return the global singleton, creating it on first call."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Destroy the singleton (useful in tests)."""
        with cls._lock:
            cls._instance = None

    # ── Counter operations ──────────────────────────────────────

    def inc_counter(self, name: str, labels: dict[str, str]) -> None:
        """Increment a labelled counter by 1."""
        key = self._label_key(name, labels)
        with self._mu:
            self.counters[key] = self.counters.get(key, 0) + 1

    # ── Histogram operations ────────────────────────────────────

    def observe_histogram(
        self,
        name: str,
        labels: dict[str, str],
        value: float,
        buckets: tuple[float, ...] = DEFAULT_BUCKETS,
    ) -> None:
        """Record an observation in the histogram."""
        key = self._label_key(name, labels)
        with self._mu:
            if key not in self.histograms:
                # Initialise bucket counts (including +Inf)
                self.histograms[key] = [(b, 0) for b in buckets] + [(float("inf"), 0)]
                self._histogram_sums[key] = 0.0
                self._histogram_counts[key] = 0
            updated: list[tuple[float, int]] = []
            for le, count in self.histograms[key]:
                if value <= le:
                    updated.append((le, count + 1))
                else:
                    updated.append((le, count))
            self.histograms[key] = updated
            self._histogram_sums[key] += value
            self._histogram_counts[key] += 1

    # ── Gauge operations ────────────────────────────────────────

    def inc_gauge(self, name: str, labels: dict[str, str]) -> None:
        """Increment a gauge by 1."""
        key = self._label_key(name, labels)
        with self._mu:
            self.gauges[key] = self.gauges.get(key, 0) + 1

    def dec_gauge(self, name: str, labels: dict[str, str]) -> None:
        """Decrement a gauge by 1."""
        key = self._label_key(name, labels)
        with self._mu:
            self.gauges[key] = self.gauges.get(key, 0) - 1

    # ── Reset (testing) ─────────────────────────────────────────

    def reset(self) -> None:
        """Clear all stored metrics."""
        with self._mu:
            self.counters.clear()
            self.histograms.clear()
            self._histogram_sums.clear()
            self._histogram_counts.clear()
            self.gauges.clear()

    # ── Prometheus text exposition ──────────────────────────────

    def collect(self) -> str:
        """Return all metrics in Prometheus text exposition format."""
        with self._mu:
            lines: list[str] = []
            self._collect_counters(lines)
            self._collect_histograms(lines)
            self._collect_gauges(lines)
        return "\n".join(lines) + "\n" if lines else ""

    # -- private helpers --

    def _collect_counters(self, lines: list[str]) -> None:
        emitted_help: set[str] = set()
        for key, value in sorted(self.counters.items()):
            name, label_str = self._parse_key(key)
            if name not in emitted_help:
                lines.append(f"# HELP {name} Total count")
                lines.append(f"# TYPE {name} counter")
                emitted_help.add(name)
            lines.append(f"{name}{{{label_str}}} {value}")

    def _collect_histograms(self, lines: list[str]) -> None:
        emitted_help: set[str] = set()
        for key in sorted(self.histograms):
            name, label_str = self._parse_key(key)
            if name not in emitted_help:
                lines.append(f"# HELP {name} Duration histogram")
                lines.append(f"# TYPE {name} histogram")
                emitted_help.add(name)
            for le, count in self.histograms[key]:
                le_str = "+Inf" if le == float("inf") else (f"{le:g}")
                lines.append(f'{name}_bucket{{{label_str},le="{le_str}"}} {count}')
            lines.append(f"{name}_sum{{{label_str}}} {self._histogram_sums[key]}")
            lines.append(f"{name}_count{{{label_str}}} {self._histogram_counts[key]}")

    def _collect_gauges(self, lines: list[str]) -> None:
        emitted_help: set[str] = set()
        for key, value in sorted(self.gauges.items()):
            name, label_str = self._parse_key(key)
            if name not in emitted_help:
                lines.append(f"# HELP {name} Gauge value")
                lines.append(f"# TYPE {name} gauge")
                emitted_help.add(name)
            lines.append(f"{name}{{{label_str}}} {value}")

    @staticmethod
    def _label_key(name: str, labels: dict[str, str]) -> str:
        """Encode metric name + labels into a single dict key."""
        sorted_labels = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}|{sorted_labels}"

    @staticmethod
    def _parse_key(key: str) -> tuple[str, str]:
        """Decode a ``_label_key`` string back into name and labels."""
        name, label_str = key.split("|", 1)
        return name, label_str


def get_metrics_registry() -> MetricsRegistry:
    """Convenience accessor for the global metrics registry."""
    return MetricsRegistry.get_instance()


# ── Starlette Middleware ────────────────────────────────────────────


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record HTTP request metrics for Prometheus scraping."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        registry = get_metrics_registry()
        method = request.method
        path = normalize_path(request.url.path)

        # Track in-progress requests
        gauge_labels = {"method": method}
        registry.inc_gauge("http_requests_in_progress", gauge_labels)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Record a 500 even if the exception propagates
            duration = time.perf_counter() - start
            registry.inc_counter(
                "http_requests_total",
                {
                    "method": method,
                    "path_template": path,
                    "status_code": "500",
                },
            )
            registry.observe_histogram(
                "http_request_duration_seconds",
                {"method": method, "path_template": path},
                duration,
            )
            raise
        finally:
            registry.dec_gauge("http_requests_in_progress", gauge_labels)

        duration = time.perf_counter() - start
        status_code = str(response.status_code)

        registry.inc_counter(
            "http_requests_total",
            {
                "method": method,
                "path_template": path,
                "status_code": status_code,
            },
        )
        registry.observe_histogram(
            "http_request_duration_seconds",
            {"method": method, "path_template": path},
            duration,
        )
        return response
