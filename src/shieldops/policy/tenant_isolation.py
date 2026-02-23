"""Tenant Resource Isolation Manager — blast-radius isolation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IsolationLevel(StrEnum):
    NONE = "none"
    SOFT = "soft"
    HARD = "hard"
    STRICT = "strict"


class ResourceType(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"
    PODS = "pods"


class ViolationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    BREACH = "breach"


# --- Models ---


class TenantBoundary(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_name: str
    namespace: str = ""
    isolation_level: IsolationLevel = IsolationLevel.SOFT
    resource_limits: dict[str, float] = Field(default_factory=dict)
    resource_usage: dict[str, float] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class IsolationViolation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    resource_type: ResourceType
    severity: ViolationSeverity
    limit_value: float = 0.0
    actual_value: float = 0.0
    message: str = ""
    detected_at: float = Field(default_factory=time.time)


# --- Manager ---


class TenantResourceIsolationManager:
    """Manages per-team/namespace blast-radius isolation with resource boundaries."""

    def __init__(
        self,
        max_tenants: int = 500,
        max_violations: int = 50000,
    ) -> None:
        self._max_tenants = max_tenants
        self._max_violations = max_violations
        self._tenants: dict[str, TenantBoundary] = {}
        self._violations: list[IsolationViolation] = []
        logger.info(
            "tenant_isolation.initialized",
            max_tenants=max_tenants,
            max_violations=max_violations,
        )

    def register_tenant(
        self,
        tenant_name: str,
        namespace: str = "",
        isolation_level: IsolationLevel = IsolationLevel.SOFT,
        resource_limits: dict[str, float] | None = None,
        **kw: Any,
    ) -> TenantBoundary:
        """Register a new tenant with resource boundaries."""
        tenant = TenantBoundary(
            tenant_name=tenant_name,
            namespace=namespace,
            isolation_level=isolation_level,
            resource_limits=resource_limits or {},
            **kw,
        )
        self._tenants[tenant.id] = tenant
        if len(self._tenants) > self._max_tenants:
            oldest = next(iter(self._tenants))
            del self._tenants[oldest]
        logger.info(
            "tenant_isolation.tenant_registered",
            tenant_id=tenant.id,
            tenant_name=tenant_name,
            isolation_level=isolation_level,
        )
        return tenant

    def update_usage(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        value: float,
    ) -> TenantBoundary | None:
        """Update resource usage for a tenant."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return None
        tenant.resource_usage[resource_type] = value
        tenant.updated_at = time.time()
        logger.info(
            "tenant_isolation.usage_updated",
            tenant_id=tenant_id,
            resource_type=resource_type,
            value=value,
        )
        return tenant

    def check_limits(self, tenant_id: str) -> list[IsolationViolation]:
        """Check if tenant exceeds any resource limits."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return []
        violations: list[IsolationViolation] = []
        for res_type, limit in tenant.resource_limits.items():
            usage = tenant.resource_usage.get(res_type, 0.0)
            if usage > limit:
                ratio = usage / limit if limit > 0 else float("inf")
                if ratio > 1.5:
                    severity = ViolationSeverity.BREACH
                elif ratio > 1.2:
                    severity = ViolationSeverity.CRITICAL
                elif ratio > 1.0:
                    severity = ViolationSeverity.WARNING
                else:
                    severity = ViolationSeverity.INFO
                try:
                    rt = ResourceType(res_type)
                except ValueError:
                    rt = ResourceType.CPU
                violation = IsolationViolation(
                    tenant_id=tenant_id,
                    resource_type=rt,
                    severity=severity,
                    limit_value=limit,
                    actual_value=usage,
                    message=f"{res_type} usage {usage} exceeds limit {limit}",
                )
                violations.append(violation)
                self._violations.append(violation)
        if len(self._violations) > self._max_violations:
            self._violations = self._violations[-self._max_violations :]
        return violations

    def get_tenant(self, tenant_id: str) -> TenantBoundary | None:
        """Retrieve a tenant by ID."""
        return self._tenants.get(tenant_id)

    def list_tenants(
        self,
        isolation_level: IsolationLevel | None = None,
    ) -> list[TenantBoundary]:
        """List tenants with optional filter."""
        results = list(self._tenants.values())
        if isolation_level is not None:
            results = [t for t in results if t.isolation_level == isolation_level]
        return results

    def list_violations(
        self,
        tenant_id: str | None = None,
        severity: ViolationSeverity | None = None,
    ) -> list[IsolationViolation]:
        """List violations with optional filters."""
        results = list(self._violations)
        if tenant_id is not None:
            results = [v for v in results if v.tenant_id == tenant_id]
        if severity is not None:
            results = [v for v in results if v.severity == severity]
        return results

    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant."""
        if tenant_id in self._tenants:
            del self._tenants[tenant_id]
            logger.info("tenant_isolation.tenant_deleted", tenant_id=tenant_id)
            return True
        return False

    def get_utilization_report(self) -> list[dict[str, Any]]:
        """Get utilization report for all tenants."""
        report: list[dict[str, Any]] = []
        for tenant in self._tenants.values():
            utilization: dict[str, float] = {}
            for res_type, limit in tenant.resource_limits.items():
                usage = tenant.resource_usage.get(res_type, 0.0)
                utilization[res_type] = round(usage / limit, 4) if limit > 0 else 0.0
            report.append(
                {
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.tenant_name,
                    "isolation_level": tenant.isolation_level,
                    "utilization": utilization,
                }
            )
        return report

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        level_counts: dict[str, int] = {}
        for t in self._tenants.values():
            level_counts[t.isolation_level] = level_counts.get(t.isolation_level, 0) + 1
        severity_counts: dict[str, int] = {}
        for v in self._violations:
            severity_counts[v.severity] = severity_counts.get(v.severity, 0) + 1
        return {
            "total_tenants": len(self._tenants),
            "total_violations": len(self._violations),
            "isolation_level_distribution": level_counts,
            "violation_severity_distribution": severity_counts,
        }
