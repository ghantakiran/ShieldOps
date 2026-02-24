"""DNS Health Monitor — resolution monitoring, propagation tracking, zone health scoring."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RecordType(StrEnum):
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    TXT = "TXT"
    NS = "NS"


class DNSHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    TIMEOUT = "timeout"
    NXDOMAIN = "nxdomain"
    SERVFAIL = "servfail"


class PropagationState(StrEnum):
    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    INCONSISTENT = "inconsistent"
    FAILED = "failed"


# --- Models ---


class DNSCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain: str
    record_type: RecordType
    resolver: str = ""
    response_time_ms: float = 0.0
    status: DNSHealthStatus = DNSHealthStatus.HEALTHY
    ttl: int = 3600
    created_at: float = Field(default_factory=time.time)


class PropagationCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain: str
    record_type: RecordType
    expected_value: str = ""
    resolvers_checked: int = 0
    resolvers_consistent: int = 0
    state: PropagationState = PropagationState.IN_PROGRESS
    created_at: float = Field(default_factory=time.time)


class ZoneHealthReport(BaseModel):
    zone: str
    total_checks: int = 0
    healthy_count: int = 0
    degraded_count: int = 0
    timeout_count: int = 0
    failure_count: int = 0
    avg_response_time_ms: float = 0.0
    health_score: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DNSHealthMonitor:
    """DNS resolution monitoring, propagation tracking, and zone health scoring."""

    def __init__(
        self,
        max_checks: int = 200000,
        timeout_ms: float = 5000,
    ) -> None:
        self._max_checks = max_checks
        self._timeout_ms = timeout_ms
        self._checks: list[DNSCheck] = []
        self._propagation_checks: list[PropagationCheck] = []
        logger.info(
            "dns_health.initialized",
            max_checks=max_checks,
            timeout_ms=timeout_ms,
        )

    def record_check(
        self,
        domain: str,
        record_type: RecordType,
        resolver: str = "",
        response_time_ms: float = 0.0,
        ttl: int = 3600,
    ) -> DNSCheck:
        """Record a DNS resolution check and compute health status."""
        status = self._compute_status(response_time_ms)
        check = DNSCheck(
            domain=domain,
            record_type=record_type,
            resolver=resolver,
            response_time_ms=response_time_ms,
            status=status,
            ttl=ttl,
        )
        self._checks.append(check)
        if len(self._checks) > self._max_checks:
            self._checks = self._checks[-self._max_checks :]
        if status != DNSHealthStatus.HEALTHY:
            logger.warning(
                "dns_health.check_unhealthy",
                check_id=check.id,
                domain=domain,
                status=status,
                response_time_ms=response_time_ms,
            )
        else:
            logger.debug("dns_health.check_recorded", check_id=check.id, domain=domain)
        return check

    def _compute_status(self, response_time_ms: float) -> DNSHealthStatus:
        """Derive health status from response time relative to timeout threshold."""
        if response_time_ms >= self._timeout_ms:
            return DNSHealthStatus.TIMEOUT
        if response_time_ms >= self._timeout_ms * 0.7:
            return DNSHealthStatus.DEGRADED
        return DNSHealthStatus.HEALTHY

    def get_check(self, check_id: str) -> DNSCheck | None:
        """Retrieve a single DNS check by ID."""
        for check in self._checks:
            if check.id == check_id:
                return check
        return None

    def list_checks(
        self,
        domain: str | None = None,
        record_type: RecordType | None = None,
        limit: int = 100,
    ) -> list[DNSCheck]:
        """List DNS checks with optional filtering."""
        results = list(self._checks)
        if domain is not None:
            results = [c for c in results if c.domain == domain]
        if record_type is not None:
            results = [c for c in results if c.record_type == record_type]
        return results[-limit:]

    def check_propagation(
        self,
        domain: str,
        record_type: RecordType,
        expected_value: str = "",
        resolvers_checked: int = 0,
        resolvers_consistent: int = 0,
    ) -> PropagationCheck:
        """Record a propagation check and compute propagation state."""
        state = self._compute_propagation_state(resolvers_checked, resolvers_consistent)
        prop = PropagationCheck(
            domain=domain,
            record_type=record_type,
            expected_value=expected_value,
            resolvers_checked=resolvers_checked,
            resolvers_consistent=resolvers_consistent,
            state=state,
        )
        self._propagation_checks.append(prop)
        logger.info(
            "dns_health.propagation_checked",
            check_id=prop.id,
            domain=domain,
            state=state,
        )
        return prop

    def _compute_propagation_state(
        self, resolvers_checked: int, resolvers_consistent: int
    ) -> PropagationState:
        """Derive propagation state from resolver consistency."""
        if resolvers_checked > 0 and resolvers_consistent == resolvers_checked:
            return PropagationState.COMPLETE
        if resolvers_checked > 0 and resolvers_consistent == 0:
            return PropagationState.FAILED
        if resolvers_checked > 0 and resolvers_consistent < resolvers_checked * 0.8:
            return PropagationState.INCONSISTENT
        return PropagationState.IN_PROGRESS

    def detect_failures(self, domain: str | None = None) -> list[DNSCheck]:
        """Return checks with failure statuses (TIMEOUT, NXDOMAIN, SERVFAIL)."""
        failure_statuses = {
            DNSHealthStatus.TIMEOUT,
            DNSHealthStatus.NXDOMAIN,
            DNSHealthStatus.SERVFAIL,
        }
        results = [c for c in self._checks if c.status in failure_statuses]
        if domain is not None:
            results = [c for c in results if c.domain == domain]
        return results

    def measure_resolution_latency(self, domain: str | None = None) -> dict[str, Any]:
        """Compute per-domain average response time in milliseconds."""
        checks = list(self._checks)
        if domain is not None:
            checks = [c for c in checks if c.domain == domain]
        domain_times: dict[str, list[float]] = {}
        for check in checks:
            domain_times.setdefault(check.domain, []).append(check.response_time_ms)
        return {d: round(sum(times) / len(times), 2) for d, times in domain_times.items()}

    def generate_zone_report(self, zone: str) -> ZoneHealthReport:
        """Generate an aggregate health report for all domains matching a zone."""
        zone_checks = [c for c in self._checks if c.domain.endswith(zone) or c.domain == zone]
        total = len(zone_checks)
        if total == 0:
            return ZoneHealthReport(zone=zone)

        healthy = sum(1 for c in zone_checks if c.status == DNSHealthStatus.HEALTHY)
        degraded = sum(1 for c in zone_checks if c.status == DNSHealthStatus.DEGRADED)
        timeout = sum(1 for c in zone_checks if c.status == DNSHealthStatus.TIMEOUT)
        failure = sum(
            1
            for c in zone_checks
            if c.status in {DNSHealthStatus.NXDOMAIN, DNSHealthStatus.SERVFAIL}
        )
        avg_rt = sum(c.response_time_ms for c in zone_checks) / total

        health_score = round((healthy / total) * 100, 1) if total > 0 else 0.0

        recommendations: list[str] = []
        if timeout > 0:
            recommendations.append(
                f"Investigate {timeout} timeout(s) — consider increasing resolver capacity."
            )
        if degraded > total * 0.3:
            recommendations.append("High degradation rate — review network path to resolvers.")
        if failure > 0:
            recommendations.append(f"Address {failure} resolution failure(s) (NXDOMAIN/SERVFAIL).")

        return ZoneHealthReport(
            zone=zone,
            total_checks=total,
            healthy_count=healthy,
            degraded_count=degraded,
            timeout_count=timeout,
            failure_count=failure,
            avg_response_time_ms=round(avg_rt, 2),
            health_score=health_score,
            recommendations=recommendations,
        )

    def list_propagation_checks(
        self,
        domain: str | None = None,
        limit: int = 50,
    ) -> list[PropagationCheck]:
        """List propagation checks with optional domain filter."""
        results = list(self._propagation_checks)
        if domain is not None:
            results = [p for p in results if p.domain == domain]
        return results[-limit:]

    def detect_ttl_anomalies(self, min_ttl: int = 60, max_ttl: int = 86400) -> list[DNSCheck]:
        """Find checks where TTL falls outside the expected range."""
        return [c for c in self._checks if c.ttl < min_ttl or c.ttl > max_ttl]

    def clear_data(self) -> None:
        """Clear all stored checks and propagation data."""
        self._checks.clear()
        self._propagation_checks.clear()
        logger.info("dns_health.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about DNS checks and propagation."""
        status_counts: dict[str, int] = {}
        record_type_counts: dict[str, int] = {}
        for check in self._checks:
            status_counts[check.status] = status_counts.get(check.status, 0) + 1
            record_type_counts[check.record_type] = record_type_counts.get(check.record_type, 0) + 1
        prop_state_counts: dict[str, int] = {}
        for prop in self._propagation_checks:
            prop_state_counts[prop.state] = prop_state_counts.get(prop.state, 0) + 1
        return {
            "total_checks": len(self._checks),
            "total_propagation_checks": len(self._propagation_checks),
            "status_distribution": status_counts,
            "record_type_distribution": record_type_counts,
            "propagation_state_distribution": prop_state_counts,
        }
