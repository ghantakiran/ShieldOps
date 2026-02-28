"""DNS Health Monitor — monitor DNS resolution health and latency."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DNSRecordType(StrEnum):
    A_RECORD = "a_record"
    CNAME = "cname"
    MX = "mx"
    TXT = "txt"
    SRV = "srv"


class DNSHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    UNREACHABLE = "unreachable"
    MISCONFIGURED = "misconfigured"


class DNSProvider(StrEnum):
    ROUTE53 = "route53"
    CLOUDFLARE = "cloudflare"
    CLOUD_DNS = "cloud_dns"
    AZURE_DNS = "azure_dns"
    CUSTOM = "custom"


# --- Models ---


class DNSRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_name: str = ""
    record_type: DNSRecordType = DNSRecordType.A_RECORD
    health: DNSHealth = DNSHealth.HEALTHY
    provider: DNSProvider = DNSProvider.ROUTE53
    resolution_ms: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DNSPolicy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_name: str = ""
    record_type: DNSRecordType = DNSRecordType.A_RECORD
    provider: DNSProvider = DNSProvider.ROUTE53
    max_resolution_ms: float = 100.0
    ttl_seconds: float = 300.0
    created_at: float = Field(default_factory=time.time)


class DNSHealthReport(BaseModel):
    total_checks: int = 0
    total_policies: int = 0
    healthy_rate_pct: float = 0.0
    by_record_type: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    failing_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class DNSHealthMonitor:
    """Monitor DNS resolution health and latency."""

    def __init__(
        self,
        max_records: int = 200000,
        max_resolution_ms: float = 100.0,
    ) -> None:
        self._max_records = max_records
        self._max_resolution_ms = max_resolution_ms
        self._records: list[DNSRecord] = []
        self._policies: list[DNSPolicy] = []
        logger.info(
            "dns_health_monitor.initialized",
            max_records=max_records,
            max_resolution_ms=max_resolution_ms,
        )

    # -- record / get / list -----------------------------------------

    def record_check(
        self,
        domain_name: str,
        record_type: DNSRecordType = DNSRecordType.A_RECORD,
        health: DNSHealth = DNSHealth.HEALTHY,
        provider: DNSProvider = DNSProvider.ROUTE53,
        resolution_ms: float = 0.0,
        details: str = "",
    ) -> DNSRecord:
        record = DNSRecord(
            domain_name=domain_name,
            record_type=record_type,
            health=health,
            provider=provider,
            resolution_ms=resolution_ms,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dns_health_monitor.check_recorded",
            record_id=record.id,
            domain_name=domain_name,
            record_type=record_type.value,
            health=health.value,
        )
        return record

    def get_check(self, record_id: str) -> DNSRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_checks(
        self,
        domain_name: str | None = None,
        record_type: DNSRecordType | None = None,
        limit: int = 50,
    ) -> list[DNSRecord]:
        results = list(self._records)
        if domain_name is not None:
            results = [r for r in results if r.domain_name == domain_name]
        if record_type is not None:
            results = [r for r in results if r.record_type == record_type]
        return results[-limit:]

    def add_policy(
        self,
        policy_name: str,
        record_type: DNSRecordType = DNSRecordType.A_RECORD,
        provider: DNSProvider = DNSProvider.ROUTE53,
        max_resolution_ms: float = 100.0,
        ttl_seconds: float = 300.0,
    ) -> DNSPolicy:
        policy = DNSPolicy(
            policy_name=policy_name,
            record_type=record_type,
            provider=provider,
            max_resolution_ms=max_resolution_ms,
            ttl_seconds=ttl_seconds,
        )
        self._policies.append(policy)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "dns_health_monitor.policy_added",
            policy_name=policy_name,
            record_type=record_type.value,
            provider=provider.value,
        )
        return policy

    # -- domain operations -------------------------------------------

    def analyze_dns_health(self, domain_name: str) -> dict[str, Any]:
        """Analyze DNS health for a specific domain."""
        records = [r for r in self._records if r.domain_name == domain_name]
        if not records:
            return {
                "domain_name": domain_name,
                "status": "no_data",
            }
        healthy_count = sum(1 for r in records if r.health == DNSHealth.HEALTHY)
        healthy_rate = round(healthy_count / len(records) * 100, 2)
        avg_resolution = round(
            sum(r.resolution_ms for r in records) / len(records),
            2,
        )
        return {
            "domain_name": domain_name,
            "check_count": len(records),
            "healthy_count": healthy_count,
            "healthy_rate": healthy_rate,
            "avg_resolution": avg_resolution,
            "meets_threshold": (avg_resolution <= self._max_resolution_ms),
        }

    def identify_failing_domains(
        self,
    ) -> list[dict[str, Any]]:
        """Find domains with repeated failures."""
        fail_counts: dict[str, int] = {}
        for r in self._records:
            if r.health in (
                DNSHealth.FAILING,
                DNSHealth.UNREACHABLE,
            ):
                fail_counts[r.domain_name] = fail_counts.get(r.domain_name, 0) + 1
        results: list[dict[str, Any]] = []
        for domain, count in fail_counts.items():
            if count > 1:
                results.append(
                    {
                        "domain_name": domain,
                        "failure_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["failure_count"],
            reverse=True,
        )
        return results

    def rank_by_resolution_time(
        self,
    ) -> list[dict[str, Any]]:
        """Rank domains by avg resolution time desc."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self._records:
            totals[r.domain_name] = totals.get(r.domain_name, 0.0) + r.resolution_ms
            counts[r.domain_name] = counts.get(r.domain_name, 0) + 1
        results: list[dict[str, Any]] = []
        for domain, total in totals.items():
            avg = round(total / counts[domain], 2)
            results.append(
                {
                    "domain_name": domain,
                    "avg_resolution_ms": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_resolution_ms"],
            reverse=True,
        )
        return results

    def detect_dns_issues(
        self,
    ) -> list[dict[str, Any]]:
        """Detect domains with >3 non-HEALTHY checks."""
        non_healthy: dict[str, int] = {}
        for r in self._records:
            if r.health != DNSHealth.HEALTHY:
                non_healthy[r.domain_name] = non_healthy.get(r.domain_name, 0) + 1
        results: list[dict[str, Any]] = []
        for domain, count in non_healthy.items():
            if count > 3:
                results.append(
                    {
                        "domain_name": domain,
                        "non_healthy_count": count,
                        "issue_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_healthy_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> DNSHealthReport:
        by_record_type: dict[str, int] = {}
        by_health: dict[str, int] = {}
        for r in self._records:
            by_record_type[r.record_type.value] = by_record_type.get(r.record_type.value, 0) + 1
            by_health[r.health.value] = by_health.get(r.health.value, 0) + 1
        healthy_count = sum(1 for r in self._records if r.health == DNSHealth.HEALTHY)
        healthy_rate = (
            round(
                healthy_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        failing = sum(1 for d in self.identify_failing_domains())
        recs: list[str] = []
        if healthy_rate < 100.0 and self._records:
            recs.append(f"Healthy rate {healthy_rate}% is below 100% threshold")
        if failing > 0:
            recs.append(f"{failing} domain(s) with repeated failures")
        issues = len(self.detect_dns_issues())
        if issues > 0:
            recs.append(f"{issues} domain(s) with DNS issues detected")
        if not recs:
            recs.append("DNS health is optimal across all domains")
        return DNSHealthReport(
            total_checks=len(self._records),
            total_policies=len(self._policies),
            healthy_rate_pct=healthy_rate,
            by_record_type=by_record_type,
            by_health=by_health,
            failing_count=failing,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("dns_health_monitor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.record_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_checks": len(self._records),
            "total_policies": len(self._policies),
            "max_resolution_ms": self._max_resolution_ms,
            "record_type_distribution": type_dist,
            "unique_domains": len({r.domain_name for r in self._records}),
        }
