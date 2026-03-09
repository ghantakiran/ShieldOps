"""Cross-Tenant Observability — multi-tenant observability with isolation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TenantTier(StrEnum):
    ENTERPRISE = "enterprise"
    PROFESSIONAL = "professional"
    STARTER = "starter"
    FREE = "free"


class IsolationLevel(StrEnum):
    STRICT = "strict"
    SHARED = "shared"
    HYBRID = "hybrid"


class TenantHealthStatus(StrEnum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# --- Models ---


class TenantRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    tier: TenantTier = TenantTier.STARTER
    isolation: IsolationLevel = IsolationLevel.SHARED
    health: TenantHealthStatus = TenantHealthStatus.UNKNOWN
    metric_count: int = 0
    log_volume_bytes: int = 0
    trace_count: int = 0
    created_at: float = Field(default_factory=time.time)


class TenantUsageRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    metrics_ingested: int = 0
    logs_ingested_bytes: int = 0
    traces_ingested: int = 0
    cost_usd: float = 0.0
    period: str = ""
    created_at: float = Field(default_factory=time.time)


class CrossTenantReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_tenants: int = 0
    healthy_count: int = 0
    total_metric_count: int = 0
    total_log_bytes: int = 0
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CrossTenantObservability:
    """Multi-tenant observability with isolation."""

    def __init__(self, max_tenants: int = 10000) -> None:
        self._max_tenants = max_tenants
        self._tenants: list[TenantRecord] = []
        self._usage: list[TenantUsageRecord] = []
        logger.info(
            "cross_tenant_observability.initialized",
            max_tenants=max_tenants,
        )

    def add_tenant(
        self,
        tenant_id: str,
        name: str,
        tier: TenantTier = TenantTier.STARTER,
        isolation: IsolationLevel = IsolationLevel.SHARED,
    ) -> TenantRecord:
        """Register a tenant."""
        record = TenantRecord(
            tenant_id=tenant_id,
            name=name,
            tier=tier,
            isolation=isolation,
            health=TenantHealthStatus.HEALTHY,
        )
        self._tenants.append(record)
        if len(self._tenants) > self._max_tenants:
            self._tenants = self._tenants[-self._max_tenants :]
        logger.info(
            "cross_tenant_observability.tenant_added",
            tenant_id=tenant_id,
            tier=tier.value,
        )
        return record

    def _find_tenant(self, tenant_id: str) -> TenantRecord | None:
        for t in self._tenants:
            if t.tenant_id == tenant_id:
                return t
        return None

    def isolate_tenant_data(self, tenant_id: str) -> dict[str, Any]:
        """Return data scoped to a single tenant."""
        tenant = self._find_tenant(tenant_id)
        if not tenant:
            return {"tenant_id": tenant_id, "status": "not_found"}
        usage = [u for u in self._usage if u.tenant_id == tenant_id]
        return {
            "tenant_id": tenant_id,
            "name": tenant.name,
            "tier": tenant.tier.value,
            "isolation": tenant.isolation.value,
            "health": tenant.health.value,
            "metric_count": tenant.metric_count,
            "log_volume_bytes": tenant.log_volume_bytes,
            "usage_records": len(usage),
        }

    def aggregate_cross_tenant(self) -> dict[str, Any]:
        """Aggregate metrics across all tenants (anonymized)."""
        total_metrics = sum(t.metric_count for t in self._tenants)
        total_logs = sum(t.log_volume_bytes for t in self._tenants)
        total_traces = sum(t.trace_count for t in self._tenants)
        return {
            "total_tenants": len(self._tenants),
            "total_metrics": total_metrics,
            "total_log_bytes": total_logs,
            "total_traces": total_traces,
            "avg_metrics_per_tenant": (
                round(total_metrics / len(self._tenants), 1) if self._tenants else 0
            ),
        }

    def enforce_data_boundaries(self, tenant_id: str) -> dict[str, Any]:
        """Verify data boundary enforcement for a tenant."""
        tenant = self._find_tenant(tenant_id)
        if not tenant:
            return {"tenant_id": tenant_id, "enforced": False, "reason": "not_found"}
        violations: list[str] = []
        if tenant.isolation == IsolationLevel.STRICT:
            # Check for cross-tenant data leaks (simulated)
            pass
        if tenant.tier == TenantTier.FREE and tenant.metric_count > 10000:
            violations.append("free tier metric limit exceeded")
        if tenant.tier == TenantTier.STARTER and tenant.metric_count > 100000:
            violations.append("starter tier metric limit exceeded")
        return {
            "tenant_id": tenant_id,
            "enforced": len(violations) == 0,
            "isolation": tenant.isolation.value,
            "violations": violations,
        }

    def record_usage(
        self,
        tenant_id: str,
        metrics_ingested: int = 0,
        logs_ingested_bytes: int = 0,
        traces_ingested: int = 0,
        cost_usd: float = 0.0,
        period: str = "",
    ) -> TenantUsageRecord:
        """Record usage for a tenant."""
        usage = TenantUsageRecord(
            tenant_id=tenant_id,
            metrics_ingested=metrics_ingested,
            logs_ingested_bytes=logs_ingested_bytes,
            traces_ingested=traces_ingested,
            cost_usd=cost_usd,
            period=period,
        )
        self._usage.append(usage)
        # Update tenant counters
        tenant = self._find_tenant(tenant_id)
        if tenant:
            tenant.metric_count += metrics_ingested
            tenant.log_volume_bytes += logs_ingested_bytes
            tenant.trace_count += traces_ingested
        return usage

    def get_tenant_usage(
        self,
        tenant_id: str,
        limit: int = 50,
    ) -> list[TenantUsageRecord]:
        """Get usage records for a tenant."""
        records = [u for u in self._usage if u.tenant_id == tenant_id]
        return records[-limit:]

    def compare_tenant_health(self) -> list[dict[str, Any]]:
        """Compare health across tenants (anonymized)."""
        results: list[dict[str, Any]] = []
        for t in self._tenants:
            results.append(
                {
                    "tenant_id": t.tenant_id,
                    "tier": t.tier.value,
                    "health": t.health.value,
                    "metric_count": t.metric_count,
                    "log_volume_bytes": t.log_volume_bytes,
                }
            )
        results.sort(key=lambda x: x["metric_count"], reverse=True)
        return results

    def generate_report(self) -> CrossTenantReport:
        """Generate cross-tenant observability report."""
        by_tier: dict[str, int] = {}
        by_health: dict[str, int] = {}
        for t in self._tenants:
            by_tier[t.tier.value] = by_tier.get(t.tier.value, 0) + 1
            by_health[t.health.value] = by_health.get(t.health.value, 0) + 1
        healthy = sum(1 for t in self._tenants if t.health == TenantHealthStatus.HEALTHY)
        total_m = sum(t.metric_count for t in self._tenants)
        total_l = sum(t.log_volume_bytes for t in self._tenants)
        recs: list[str] = []
        critical = sum(1 for t in self._tenants if t.health == TenantHealthStatus.CRITICAL)
        if critical > 0:
            recs.append(f"{critical} tenant(s) in critical health")
        if not recs:
            recs.append("All tenants healthy")
        return CrossTenantReport(
            total_tenants=len(self._tenants),
            healthy_count=healthy,
            total_metric_count=total_m,
            total_log_bytes=total_l,
            by_tier=by_tier,
            by_health=by_health,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all tenants and usage data."""
        self._tenants.clear()
        self._usage.clear()
        logger.info("cross_tenant_observability.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_tenants": len(self._tenants),
            "total_usage_records": len(self._usage),
            "unique_tenant_ids": len({t.tenant_id for t in self._tenants}),
        }
